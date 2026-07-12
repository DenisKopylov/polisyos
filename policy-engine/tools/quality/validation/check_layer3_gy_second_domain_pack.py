#!/usr/bin/env python3
"""Build and verify the owner-derived GY-N10a second-domain substrate pack.

The tool intentionally owns only frozen evidence artifacts. It does not create
an S0/L6 registry or alter runtime behavior: when an existing owner cannot
persist or consume an education-domain fact, the output records a typed gap.
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import copy
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from polisyos.data_requirement import (
    DataQualityMinimums,
    DataRequirementScope,
    DataRequirementSpec,
)
from polisyos.pdc import SearchTerminalKind, gy_content_hash
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionReceipt,
    AcquisitionWorldSnapshot,
    RealAcquisitionOwnerGateway,
    run_acquisition_closed_loop,
    validate_acquisition_receipt,
)
from polisyos.runtime.quality.design_problem import (
    AuthorityProfile,
    CandidateLever,
    CandidateLeverSpace,
    DesignConstraint,
    DesignObjective,
    DesignProblem,
    DesignStakeholder,
    EvidenceAcquisitionNeeds,
    EvidenceNeed,
    JurisdictionTimeSemantics,
    NLProvenance,
    OutcomeOfInterest,
)
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleController,
    GenerationCycleRun,
    validate_generation_cycle_run,
)
from polisyos.runtime.quality.grounding_admission import GroundingAdmissionLedger
from polisyos.runtime.quality.intervention_substrate import (
    InterventionSubstrateError,
    load_l6_intervention_substrate,
    resolve_intervention_lever,
)
from polisyos.runtime.quality.substrate_registry import (
    DEFAULT_L2_SCHOLAR_KG_PATH,
    SubstrateRegistry,
    build_substrate_registry,
    build_substrate_registry_from_existing_catalogs,
    default_substrate_catalog_paths,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState

SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy_second_domain_pack.v1"
RULE_VERSION = "policyos.layer3.gy.n10a.owner_derived_second_domain_pack.v1"
PRODUCER = "tools.quality.validation.check_layer3_gy_second_domain_pack"
CENSUS_OUTPUT = "architecture/policy_design_case/layer3_gy_second_domain_census.json"
PACK_OUTPUT = "architecture/policy_design_case/layer3_gy_second_domain_pack.json"
SMOKE_PROBLEM_OUTPUT = "architecture/policy_design_case/layer3_gy_second_domain_smoke_design_problem.json"
CYCLE_TRACE_OUTPUT = "architecture/policy_design_case/layer3_gy_second_domain_cycle_entry_trace.json"
GAP_REPORT_OUTPUT = "architecture/policy_design_case/layer3_gy_second_domain_free_grow_gaps.json"
N10A_BASE_COMMIT = "26cc7cc03efc9da44362dc2914a5bde8ac8f7e73"
N10A_PROOF_HEAD_COMMIT = "d8a8cf076da6233c66b0a90010647c0d437e81c4"
_SUBSTRATE_REGISTRY_OWNER = "runtime.quality.substrate_registry"
_SUBSTRATE_REGISTRY_PRODUCER = (
    "polisyos.runtime.quality.substrate_registry."
    "build_substrate_registry_from_existing_catalogs"
)
_CYCLE_SUBSTRATE_MUTATION_EXPECTED_CODES = {
    "coordinated_query_rewrite": "cycle_substrate_registry_query_census_mismatch",
    "coherent_registry_forgery": "cycle_substrate_registry_owner_rederive_mismatch",
    "registry_version_rewrite": "cycle_substrate_registry_version_id_mismatch",
    "lever_registry_binding_rewrite": "cycle_substrate_lever_registry_binding_mismatch",
    "alternate_valid_l2_repoint": (
        "cycle_substrate_registry_selected_entry_not_query_owner"
    ),
}

ARTIFACT_OUTPUTS = (
    CENSUS_OUTPUT,
    PACK_OUTPUT,
    SMOKE_PROBLEM_OUTPUT,
    CYCLE_TRACE_OUTPUT,
    GAP_REPORT_OUTPUT,
)

_CONTENT_HASH_ALLOWED_EXCLUSIONS: dict[str, frozenset[str]] = {
    "census_content_hash": frozenset({"runtime_metrics"}),
    "manifest_content_hash": frozenset({"runtime_metrics"}),
    "trace_content_hash": frozenset({"runtime_metrics"}),
}

_TASK_SCOPE_ALLOWED_EXACT = frozenset(
    {
        "architecture/generated_artifacts.toml",
        "architecture/policy_design_case/layer3_gy_generation_cycle_disposition_ledger.json",
        "docs/reference/generated-artifacts.md",
        "docs/superpowers/plans/2026-07-09-second-domain-pack.md",
        "docs/superpowers/plans/2026-07-10-second-domain-pack-provenance-repair.md",
        "docs/superpowers/specs/2026-07-09-second-domain-pack-design.md",
        "docs/superpowers/specs/2026-07-10-second-domain-pack-provenance-repair-design.md",
        "tests/unit/runtime/quality/test_second_domain_pack.py",
        "tools/quality/validation/check_layer3_gy_second_domain_pack.py",
    }
)
_TASK_SCOPE_ALLOWED_PREFIXES = (
    "architecture/policy_design_case/layer3_gy_second_domain_",
)

_CANDIDATE_SPECS: dict[str, dict[str, tuple[str, ...]]] = {
    "health": {
        "l1_canonical_vars": (
            "health_outcomes",
            "vaccination_coverage",
            "life_expectancy",
            "neonatal_mortality",
            "noncommunicable_disease_mortality",
            "tuberculosis_incidence",
            "infant_mortality",
            "hiv_prevalence",
            "malaria_incidence",
            "child_stunting",
        ),
        "l2_prefixes": ("health.",),
        "transport_tokens": ("burden", "coverage", "mortality", "incidence"),
    },
    "education": {
        "l1_canonical_vars": (
            "education_outcomes",
            "tertiary_enrollment",
            "preschool_enrollment",
            "school_quality",
            "years_of_schooling",
            "stem_graduates",
            "education_spending",
            "gender_parity_index",
        ),
        "l2_prefixes": ("education.",),
        "transport_tokens": ("spending", "quality", "schooling"),
    },
    "environment_energy_transition": {
        "l1_canonical_vars": (
            "emissions",
            "energy_mix",
            "energy_price",
            "energy_intensity",
            "air_quality_index",
            "electricity_access",
            "forest_cover",
            "water_stress",
        ),
        "l2_prefixes": ("climate.", "energy.", "environmental."),
        "transport_tokens": ("energy", "price", "intensity", "air_quality"),
    },
}


class OwnerDataUnavailableError(RuntimeError):
    """Raised when an owner database is absent from the caller's data mount."""


class GapWitnessTargetMissingError(RuntimeError):
    """Raised when a recorded free-grow seam no longer resolves in its owner."""


class SourceHashCheckoutPathError(ValueError):
    """Raised when evidence would bind a checkout-specific source path."""


@dataclass(frozen=True)
class GapWitnessSpec:
    """Canonical, segment-scoped source witness for one typed free-grow gap."""

    source_path: str
    symbol: str


@dataclass(frozen=True)
class HistoricalL2QueryEvidence:
    """Immutable N10a census evidence for the selected L2 owner query."""

    candidate_id: str
    query_id: str
    query_content_hash: str
    response_content_hash: str
    owner_query_source_ref: str


GAP_WITNESS_SPECS: dict[str, GapWitnessSpec] = {
    "s0_to_l6_world_slot_bridge_missing": GapWitnessSpec(
        source_path="src/polisyos/runtime/quality/intervention_substrate.py",
        symbol="resolve_intervention_lever",
    ),
    "owner_registration_derivation_missing": GapWitnessSpec(
        source_path="src/polisyos/runtime/quality/acquisition_planner.py",
        symbol="_project_owner_artifacts_into_world",
    ),
    "journal_raw_evidence_persistence_missing": GapWitnessSpec(
        source_path="src/polisyos/runtime/quality/acquisition_planner.py",
        symbol="run_acquisition_closed_loop",
    ),
    "s0_to_n4_l6_bridge_missing": GapWitnessSpec(
        source_path="src/polisyos/runtime/quality/design_generation.py",
        symbol="derive_lever_space_prompt_slice",
    ),
    "s0_to_n5_wmr_bridge_missing": GapWitnessSpec(
        source_path="src/polisyos/runtime/quality/generation_cycle.py",
        symbol="_build_boundary_world_model_record",
    ),
    "n8_transport_tuple_hardcode": GapWitnessSpec(
        source_path="src/polisyos/runtime/quality/generation_cycle.py",
        symbol="_build_candidate_selection_diagram",
    ),
    "n6_single_terminal_validation_gap": GapWitnessSpec(
        source_path="src/polisyos/runtime/quality/generation_cycle.py",
        symbol="validate_generation_cycle_run",
    ),
}


class _UnavailableOwnerGenerationPort:
    """Return an owner-unavailable result so N6 exercises its real fallback path."""

    async def __call__(self, problem: DesignProblem, *, cycle_index: int) -> object:
        """Preserve a typed N4-unavailable condition without fabricating a candidate."""

        del problem, cycle_index
        return SimpleNamespace(status="generation_unavailable", candidates=(), surrogate_rankings=())


@lru_cache(maxsize=4)
def _cached_owner_substrate_registry(repo_root: str) -> SubstrateRegistry:
    """Build the canonical S0 registry once per checkout for E1 reuse."""

    return build_substrate_registry_from_existing_catalogs(Path(repo_root))


def declared_outputs() -> list[str]:
    """Return every frozen artifact generated by this owner."""

    return list(ARTIFACT_OUTPUTS)


def build_live_bundle(repo_root: Path) -> dict[str, Any]:
    """Re-derive the complete pack from DCAT, SKG, S0/L6, and N6 owners."""

    started = time.monotonic()
    root = repo_root.resolve()
    paths = _owner_paths(root)
    query_timings: dict[str, float] = {}
    census = _build_census(root, paths, query_timings)
    source_facts = _build_selected_domain_facts(root, paths, census, query_timings)
    source_facts["n7_attempt"] = _load_historical_n7_attempt(
        root,
        source_facts,
    ) or _run_n7_live_attempt(root, source_facts)
    substrate_input = _build_cycle_substrate_input_projection(census, source_facts)
    smoke_problem = _build_smoke_problem(census, source_facts)
    cycle_trace = _build_cycle_trace(root, smoke_problem)
    gaps = _build_gap_report(root, source_facts, cycle_trace)
    pack = _build_pack(
        root,
        census,
        source_facts,
        smoke_problem,
        cycle_trace,
        gaps,
        substrate_input,
    )
    return {
        "census": census,
        "pack": pack,
        "smoke_problem": smoke_problem,
        "cycle_trace": cycle_trace,
        "gaps": gaps,
        "runtime_metrics": {
            "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
            "query_timings_seconds": query_timings,
            "owner_data_paths": {
                "l1_dcat": _repo_relative(paths["l1_dcat"], root),
                "l2_skg": _repo_relative(paths["l2_skg"], root),
            },
        },
    }


def validate_bundle_payloads(bundle: Mapping[str, Any], repo_root: Path) -> list[dict[str, Any]]:
    """Validate frozen content, owner evidence, distinctness, and terminal honesty."""

    root = repo_root.resolve()
    issues: list[dict[str, Any]] = []
    census = _mapping(bundle.get("census"))
    pack = _mapping(bundle.get("pack"))
    smoke_problem = _mapping(bundle.get("smoke_problem"))
    cycle_trace = _mapping(bundle.get("cycle_trace"))
    gaps = _mapping(bundle.get("gaps"))

    _validate_artifact_hash(census, "census_content_hash", issues)
    _validate_artifact_hash(pack, "manifest_content_hash", issues)
    _validate_artifact_hash(smoke_problem, "smoke_problem_content_hash", issues)
    _validate_artifact_hash(cycle_trace, "trace_content_hash", issues)
    _validate_artifact_hash(gaps, "gap_report_content_hash", issues)

    if pack.get("census_content_hash") != census.get("census_content_hash"):
        issues.append({"code": "pack_census_ref_drift"})
    if pack.get("smoke_problem_content_hash") != smoke_problem.get("smoke_problem_content_hash"):
        issues.append({"code": "pack_smoke_problem_ref_drift"})
    if pack.get("cycle_trace_content_hash") != cycle_trace.get("trace_content_hash"):
        issues.append({"code": "pack_cycle_trace_ref_drift"})
    if pack.get("gap_report_content_hash") != gaps.get("gap_report_content_hash"):
        issues.append({"code": "pack_gap_report_ref_drift"})

    _validate_census_selection(census, issues)
    _validate_cycle_substrate_registry(root, census, pack, issues)
    _validate_owner_derived_entries(census, pack, issues)
    _validate_n7_attempt(root, pack, issues)
    _validate_distinctness(root, pack, issues)
    _validate_coverage_denominators(census, pack, gaps, issues)
    _validate_gap_witnesses(root, gaps, issues)
    _validate_smoke_terminal(smoke_problem, cycle_trace, issues)
    _validate_zero_engine_code(root, pack, issues)
    return issues


def validate(repo_root: Path) -> dict[str, Any]:
    """Validate frozen artifacts without reopening external owner stores."""

    started = time.monotonic()
    root = repo_root.resolve()
    try:
        bundle = _load_frozen_bundle(root)
    except FileNotFoundError as exc:
        return {
            "status": "fail",
            "issues": [{"code": "second_domain_pack_artifact_missing", "error": str(exc)}],
            "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
        }
    issues = validate_bundle_payloads(bundle, root)
    census_metrics = _mapping(_mapping(bundle.get("census")).get("runtime_metrics"))
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
        "query_timings_seconds": _mapping(census_metrics.get("query_timings_seconds")),
    }


def rederive_audit(repo_root: Path) -> dict[str, Any]:
    """Rebuild owner facts and require byte-for-byte agreement with frozen output."""

    started = time.monotonic()
    root = repo_root.resolve()
    try:
        frozen = _load_frozen_bundle(root)
        live = build_live_bundle(root)
    except OwnerDataUnavailableError as exc:
        return {
            "status": "fail",
            "issues": [{"code": "owner_data_unavailable", "error": str(exc)}],
            "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
        }
    issues = validate_bundle_payloads(live, root)
    for name in ("census", "pack", "smoke_problem", "cycle_trace", "gaps"):
        if _content_bound_canonical_json(live[name]) != _content_bound_canonical_json(
            frozen[name]
        ):
            issues.append({"code": "owner_rederive_drift", "artifact": name})
    metrics = _mapping(live.get("runtime_metrics"))
    n7_metrics = _mapping(_mapping(live.get("pack")).get("runtime_metrics")).get(
        "n7_acquisition"
    )
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
        "query_timings_seconds": _mapping(metrics.get("query_timings_seconds")),
        "n7_capture_operational_metadata": {
            "receipt_generated_at": _mapping(n7_metrics).get("receipt_generated_at"),
            "planner_report_generated_at": _mapping(n7_metrics).get(
                "planner_report_generated_at"
            ),
            "owner_capture_times": _mapping(n7_metrics).get("owner_capture_times"),
        },
    }


def corrupt_field_drift_check(repo_root: Path) -> dict[str, Any]:
    """Exercise owner provenance, distinctness, terminal, and code-scope mutations."""

    started = time.monotonic()
    root = repo_root.resolve()
    bundle = _load_frozen_bundle(root)
    corrupted = copy.deepcopy(bundle)
    components = _mapping(corrupted["pack"].get("components"))
    lever_component = _mapping(components.get("lever_vocabulary"))
    lever_entries = _list_of_mappings(lever_component.get("entries"))
    lever_entries.append(
        {
            "lever_id": "hand_authored_entry",
            "instrument": "hand.authored",
            "status": "candidate_unbound",
        }
    )
    lever_entries.append(
        {
            "lever_id": "first_vertical_lever",
            "instrument": "policy.credit_access",
            "status": "candidate_unbound",
        }
    )
    lever_component["entries"] = lever_entries
    components["lever_vocabulary"] = lever_component
    corrupted["pack"]["components"] = components
    outcomes_component = _mapping(components.get("outcomes"))
    outcome_entries = _list_of_mappings(outcomes_component.get("entries"))
    if outcome_entries:
        outcome_entries[0]["canonical_var"] = "avg_income"
    if len(outcome_entries) > 1:
        outcome_entries[1]["dataset_ids"] = ["spoofed-dataset-id"]
    outcomes_component["entries"] = outcome_entries
    components["outcomes"] = outcomes_component
    transport_component = _mapping(components.get("transport_context"))
    covariates = _list_of_mappings(transport_component.get("covariates"))
    if covariates:
        covariates[0]["canonical_var"] = "state_capacity"
    transport_component["covariates"] = covariates
    components["transport_context"] = transport_component
    corrupted["pack"]["components"] = components
    registry_owner = _mapping(
        _mapping(corrupted["pack"].get("owner_query_results")).get("s0_registry")
    )
    registry_payload = _mapping(registry_owner.get("registry_payload"))
    registry_entries = _list_of_mappings(registry_payload.get("entries"))
    if registry_entries:
        registry_entries[0]["family_id"] = "corrupt_drift_shaped_family"
        registry_payload["entries"] = registry_entries
        registry_owner["registry_payload"] = registry_payload
        corrupted["pack"]["owner_query_results"]["s0_registry"] = registry_owner
    addressing = _mapping(corrupted["pack"].get("content_addressing"))
    addressing["historical_source_pack_content_hash"] = corrupted["pack"].get(
        "manifest_content_hash"
    )
    corrupted["pack"]["content_addressing"] = addressing
    cycle_run = _mapping(corrupted["cycle_trace"].get("generation_cycle_run"))
    trace_cycles = _list_of_mappings(
        cycle_run.get("cycles")
    )
    if trace_cycles:
        trace_cycles[0]["terminal_kind"] = "crash"
    cycle_run["cycles"] = trace_cycles
    corrupted["cycle_trace"]["generation_cycle_run"] = cycle_run
    code_scope = _mapping(corrupted["pack"].get("zero_engine_code"))
    code_scope["proof_head_commit"] = "HEAD"
    code_scope["changed_engine_paths"] = [
        "src/polisyos/runtime/quality/fabricated.py"
    ]
    code_scope["out_of_scope_paths"] = ["README.md"]
    corrupted["pack"]["zero_engine_code"] = code_scope
    n7_attempt = _mapping(corrupted["pack"].get("n7_acquisition"))
    receipt_content = _mapping(n7_attempt.get("receipt_content"))
    receipt_content["generated_at"] = "2026-07-10T00:00:00Z"
    n7_attempt["receipt_content"] = receipt_content
    n7_attempt["receipt_content_hash"] = _hash(receipt_content)
    corrupted["pack"]["n7_acquisition"] = n7_attempt
    n7_operational = _mapping(
        _mapping(corrupted["pack"].get("runtime_metrics")).get("n7_acquisition")
    )
    n7_operational["receipt"] = _reconstruct_n7_receipt_payload(
        receipt_content,
        n7_operational,
    )
    corrupted["pack"]["runtime_metrics"]["n7_acquisition"] = n7_operational
    gap_records = _list_of_mappings(corrupted["gaps"].get("gaps"))
    if gap_records:
        first_witness = _mapping(_mapping(gap_records[0].get("owner_evidence")).get("seam_witness"))
        if first_witness.get("source_path"):
            first_witness["source_path"] = str(root / str(first_witness["source_path"]))
        first_evidence = _mapping(gap_records[0].get("owner_evidence"))
        first_evidence["seam_witness"] = first_witness
        gap_records[0]["owner_evidence"] = first_evidence
    if len(gap_records) > 1:
        second_witness = _mapping(_mapping(gap_records[1].get("owner_evidence")).get("seam_witness"))
        second_witness["symbol"] = "__gy_n10a_missing_target__"
        second_evidence = _mapping(gap_records[1].get("owner_evidence"))
        second_evidence["seam_witness"] = second_witness
        gap_records[1]["owner_evidence"] = second_evidence
    mutated_gaps = _mapping(corrupted["gaps"])
    mutated_gaps["gaps"] = [
        _with_content_hash(gap, "gap_content_hash") for gap in gap_records
    ]
    corrupted["gaps"] = _with_content_hash(mutated_gaps, "gap_report_content_hash")
    corrupted["pack"]["gap_report_content_hash"] = corrupted["gaps"][
        "gap_report_content_hash"
    ]
    corrupted["pack"] = _with_content_hash(
        corrupted["pack"],
        "manifest_content_hash",
        excluded_fields=("runtime_metrics",),
    )
    issues = validate_bundle_payloads(corrupted, root)
    mutation_results: list[dict[str, Any]] = []
    per_mutation_missing: set[str] = set()
    all_issues = list(issues)
    for mutation_id, mutation in _cycle_substrate_corruption_bundles(bundle):
        mutation_issues = validate_bundle_payloads(mutation, root)
        mutation_codes = sorted(
            {
                str(issue.get("code"))
                for issue in mutation_issues
                if issue.get("code")
            }
        )
        mutation_results.append(
            {"mutation_id": mutation_id, "detected_codes": mutation_codes}
        )
        expected_mutation_code = _CYCLE_SUBSTRATE_MUTATION_EXPECTED_CODES.get(
            mutation_id
        )
        if expected_mutation_code is None:
            per_mutation_missing.add(f"{mutation_id}:mutation_expectation_missing")
        elif expected_mutation_code not in mutation_codes:
            per_mutation_missing.add(f"{mutation_id}:{expected_mutation_code}")
        all_issues.extend(mutation_issues)
    codes = sorted(
        {str(issue.get("code")) for issue in all_issues if issue.get("code")}
    )
    expected = {
        "pack_entry_not_owner_derived",
        "pack_entry_owner_projection_drift",
        "distinctness_lever_overlap",
        "distinctness_outcome_overlap",
        "distinctness_covariate_overlap",
        "smoke_terminal_not_honest",
        "historical_receipt_rebased_to_moving_head",
        "free_grow_violated_by_code_change",
        "free_grow_violated_by_scope_change",
        "capture_time_content_bound",
        "source_hash_checkout_path_dependent",
        "gap_witness_target_missing",
        "cycle_substrate_registry_payload_invalid",
        "cycle_substrate_registry_owner_rederive_mismatch",
        "cycle_substrate_registry_query_census_mismatch",
        "cycle_substrate_registry_version_id_mismatch",
        "cycle_substrate_lever_registry_binding_mismatch",
        "cycle_substrate_registry_selected_entry_not_query_owner",
        "cycle_substrate_input_content_hash_mismatch",
        "historical_source_pack_content_hash_mismatch",
        "n7_attempt_input_content_hash_mismatch",
        "n7_operational_receipt_duplicate",
    }
    missing = sorted(expected.difference(codes).union(per_mutation_missing))
    if missing:
        issues.append({"code": "corrupt_field_drift_not_detected", "missing": missing})
    return {
        "status": "fail" if not missing else "pass",
        "issues": [{"code": "corrupt_field_drift_detected", "detected": codes}, *issues],
        "cycle_substrate_mutation_results": mutation_results,
        "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
    }


def _cycle_substrate_corruption_bundles(
    bundle: Mapping[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """Build isolated coherent mutations for each cycle-substrate trust edge."""

    mutations: list[tuple[str, dict[str, Any]]] = []

    query_rewrite = copy.deepcopy(bundle)
    query_pack = query_rewrite["pack"]
    query = query_pack["owner_query_results"]["l2_selected_levers"]
    original_query_id = query["query_id"]
    shaped_query_id = "coordinated_shaped_query"
    owner_query = query_rewrite["census"]["owner_queries"].pop(original_query_id)
    owner_query["query_id"] = shaped_query_id
    owner_query["sql"] += "\n-- coordinated query rewrite"
    owner_query["query_content_hash"] = _hash(
        {
            "sql": owner_query["sql"],
            "parameters": _json_value(owner_query["parameters"]),
        }
    )
    query_rewrite["census"]["owner_queries"][shaped_query_id] = owner_query
    query.update(
        {
            "query_id": shaped_query_id,
            "query_content_hash": owner_query["query_content_hash"],
            "response_content_hash": owner_query["response_content_hash"],
        }
    )
    chosen = query_pack["selected_domain"]
    census_query = query_rewrite["census"]["candidates"][chosen]["l2_scholar_kg"]
    census_query.update(
        {
            "query_id": query["query_id"],
            "query_content_hash": query["query_content_hash"],
            "response_content_hash": query["response_content_hash"],
        }
    )
    query_rewrite["census"] = _with_content_hash(
        query_rewrite["census"],
        "census_content_hash",
        excluded_fields=("runtime_metrics",),
    )
    query_pack["census_content_hash"] = query_rewrite["census"][
        "census_content_hash"
    ]
    selection = query_pack["components"]["substrate_registry"][
        "selection_evidence"
    ]
    selection.update(
        {
            "query_id": query["query_id"],
            "query_content_hash": query["query_content_hash"],
            "query_response_content_hash": query["response_content_hash"],
        }
    )
    query_pack["components"]["grounding_reference_coverage"]["owner_query"] = {
        "query_id": query["query_id"],
        "query_content_hash": query["query_content_hash"],
        "response_content_hash": query["response_content_hash"],
    }
    for lever in query_pack["components"]["lever_vocabulary"]["entries"]:
        lever["owner_evidence"].update(
            {
                "query_id": query["query_id"],
                "query_content_hash": query["query_content_hash"],
                "query_response_content_hash": query["response_content_hash"],
            }
        )
        rehashed = _with_content_hash(lever, "entry_content_hash")
        lever.clear()
        lever.update(rehashed)
    _rehash_cycle_substrate_mutation(query_rewrite)
    mutations.append(("coordinated_query_rewrite", query_rewrite))

    forged_owner = copy.deepcopy(bundle)
    forged_pack = forged_owner["pack"]
    registry = SubstrateRegistry.model_validate(
        forged_pack["owner_query_results"]["s0_registry"]["registry_payload"]
    )
    selected = set(
        forged_pack["components"]["substrate_registry"]["selected_entry_hashes"]
    )
    removable = next(
        entry for entry in registry.entries if entry.entry_content_hash not in selected
    )
    forged_registry = build_substrate_registry(
        (entry for entry in registry.entries if entry != removable),
        producer_ref=registry.producer_ref,
        source_catalog_refs=registry.source_catalog_refs,
    )
    registry_owner = forged_pack["owner_query_results"]["s0_registry"]
    registry_owner.update(
        {
            "registry_payload": forged_registry.model_dump(mode="json"),
            "content_hash": forged_registry.content_hash,
            "substrate_version_id": forged_registry.substrate_version_id,
        }
    )
    registry_component = forged_pack["components"]["substrate_registry"]
    registry_component.update(
        {
            "content_hash": forged_registry.content_hash,
            "substrate_version_id": forged_registry.substrate_version_id,
        }
    )
    forged_pack["components"]["owner_writability"]["s0_registry_content_hash"] = (
        forged_registry.content_hash
    )
    _rehash_cycle_substrate_mutation(forged_owner)
    mutations.append(("coherent_registry_forgery", forged_owner))

    version_rewrite = copy.deepcopy(bundle)
    version_pack = version_rewrite["pack"]
    shaped_version = "substrate_version_ffffffffffffffff"
    version_pack["owner_query_results"]["s0_registry"][
        "substrate_version_id"
    ] = shaped_version
    version_pack["owner_query_results"]["s0_registry"]["registry_payload"][
        "substrate_version_id"
    ] = shaped_version
    version_pack["components"]["substrate_registry"][
        "substrate_version_id"
    ] = shaped_version
    _rehash_cycle_substrate_mutation(version_rewrite)
    mutations.append(("registry_version_rewrite", version_rewrite))

    lever_rewrite = copy.deepcopy(bundle)
    lever_pack = lever_rewrite["pack"]
    lever = lever_pack["components"]["lever_vocabulary"]["entries"][0]
    lever["selected_registry_entry_hash"] = "sha256:" + "0" * 64
    rehashed_lever = _with_content_hash(lever, "entry_content_hash")
    lever.clear()
    lever.update(rehashed_lever)
    _rehash_cycle_substrate_mutation(lever_rewrite)
    mutations.append(("lever_registry_binding_rewrite", lever_rewrite))

    alternate_l2 = copy.deepcopy(bundle)
    alternate_pack = alternate_l2["pack"]
    alternate_registry = SubstrateRegistry.model_validate(
        alternate_pack["owner_query_results"]["s0_registry"]["registry_payload"]
    )
    selected_hash = alternate_pack["components"]["substrate_registry"][
        "selected_entry_hashes"
    ][0]
    other_l2 = next(
        entry
        for entry in alternate_registry.entries
        if entry.layer.value == "L2" and entry.entry_content_hash != selected_hash
    )
    other_source_ref = next(
        ref.split("#", 1)[0]
        for ref in (*other_l2.provenance_refs, *other_l2.authority_refs)
        if ref.startswith("repo://")
    )
    alternate_pack["components"]["substrate_registry"][
        "selected_entry_hashes"
    ] = [other_l2.entry_content_hash]
    alternate_pack["components"]["substrate_registry"]["selection_evidence"][
        "owner_query_source_ref"
    ] = other_source_ref
    alternate_pack["owner_query_results"]["l2_selected_levers"][
        "owner_query_source_ref"
    ] = other_source_ref
    alternate_chosen = alternate_pack["selected_domain"]
    alternate_l2["census"]["candidates"][alternate_chosen]["l2_scholar_kg"][
        "owner_query_source_ref"
    ] = other_source_ref
    alternate_l2["census"] = _with_content_hash(
        alternate_l2["census"],
        "census_content_hash",
        excluded_fields=("runtime_metrics",),
    )
    alternate_pack["census_content_hash"] = alternate_l2["census"][
        "census_content_hash"
    ]
    for lever in alternate_pack["components"]["lever_vocabulary"]["entries"]:
        lever["selected_registry_entry_hash"] = other_l2.entry_content_hash
        rehashed = _with_content_hash(lever, "entry_content_hash")
        lever.clear()
        lever.update(rehashed)
    _rehash_cycle_substrate_mutation(alternate_l2)
    mutations.append(("alternate_valid_l2_repoint", alternate_l2))

    return mutations


def _rehash_cycle_substrate_mutation(bundle: dict[str, Any]) -> None:
    """Refresh only hashes downstream of a coherent cycle-substrate mutation."""

    pack = bundle["pack"]
    pack["content_addressing"]["substrate_input_content_hash"] = (
        second_domain_substrate_input_content_hash(pack)
    )
    bundle["pack"] = _with_content_hash(
        pack,
        "manifest_content_hash",
        excluded_fields=("runtime_metrics",),
    )


def write(repo_root: Path) -> dict[str, Any]:
    """Write byte-stable generated artifacts after owner rederivation."""

    started = time.monotonic()
    root = repo_root.resolve()
    bundle = build_live_bundle(root)
    _preserve_frozen_operational_metrics(bundle, root)
    by_path = {
        CENSUS_OUTPUT: bundle["census"],
        PACK_OUTPUT: bundle["pack"],
        SMOKE_PROBLEM_OUTPUT: bundle["smoke_problem"],
        CYCLE_TRACE_OUTPUT: bundle["cycle_trace"],
        GAP_REPORT_OUTPUT: bundle["gaps"],
    }
    for relative_path, payload in by_path.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_canonical_json(payload) + "\n", encoding="utf-8")
    issues = validate_bundle_payloads(bundle, root)
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "outputs": declared_outputs(),
        "query_timings_seconds": _mapping(bundle["runtime_metrics"].get("query_timings_seconds")),
        "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
    }


def _owner_paths(root: Path) -> dict[str, Path]:
    paths = default_substrate_catalog_paths(root)
    l1_dcat = paths.l1_dcat_path
    l2_skg = root / DEFAULT_L2_SCHOLAR_KG_PATH
    missing = [path for path in (l1_dcat, l2_skg) if not path.is_file()]
    if missing:
        raise OwnerDataUnavailableError(
            "canonical owner data is unavailable: " + ", ".join(str(path) for path in missing)
        )
    return {"l1_dcat": l1_dcat, "l2_skg": l2_skg}


def _build_census(
    root: Path,
    paths: Mapping[str, Path],
    query_timings: dict[str, float],
) -> dict[str, Any]:
    comparator = _first_vertical_comparator(root)
    l1_rows, l1_query = _l1_candidate_aggregate(paths["l1_dcat"], query_timings)
    l2_rows, l2_query = _l2_candidate_aggregate(paths["l2_skg"], query_timings)
    l2_query["owner_query_source_ref"] = (
        "repo://" + _repo_relative_mounted_evidence_path(paths["l2_skg"], root)
    )
    l2_measure_names, l2_measure_query = _l2_candidate_measure_names(
        paths["l2_skg"], query_timings
    )
    registry = _cached_owner_substrate_registry(root.as_posix())
    l6_bundle = load_l6_intervention_substrate(root)
    cg3_application_scope = str(
        GroundingAdmissionLedger.model_fields["application_scope"].default
    )
    l1_by_var = {str(row["canonical_var"]): row for row in l1_rows}
    l2_by_candidate = {str(row["candidate_id"]): row for row in l2_rows}
    candidates: dict[str, dict[str, Any]] = {}
    for candidate_id, spec in _CANDIDATE_SPECS.items():
        configured = list(spec["l1_canonical_vars"])
        rows = [l1_by_var[name] for name in configured if name in l1_by_var]
        missing = [name for name in configured if name not in l1_by_var]
        l2 = l2_by_candidate[candidate_id]
        top_levers = _list_of_mappings(l2.get("top_levers"))
        exact_measures = set(l2_measure_names.get(candidate_id, ()))
        transport_tokens = tuple(str(token) for token in spec["transport_tokens"])
        transport_vars = sorted(
            str(row["canonical_var"])
            for row in rows
            if str(row["canonical_var"]) in exact_measures
            and any(token in str(row["canonical_var"]) for token in transport_tokens)
        )
        lever_feasibility = _census_lever_feasibility(
            candidate_id=candidate_id,
            top_levers=top_levers,
            registry=registry,
            l6_bundle=l6_bundle,
            cg3_application_scope=cg3_application_scope,
        )
        outcome_overlap = sorted(
            set(configured).intersection(set(comparator["outcome_canonical_vars"]))
        )
        lever_overlap = sorted(
            {
                str(lever.get("cause"))
                for lever in top_levers
                if str(lever.get("cause")) in set(comparator["lever_vocabulary"])
            }
        )
        panel_count = sum(bool(row.get("panel_shape")) for row in rows)
        nonpanel_count = len(rows) - panel_count
        candidates[candidate_id] = {
            "candidate_id": candidate_id,
            "selection_input": {
                "kind": "task_supplied_domain_query_selectors",
                "l1_canonical_vars": configured,
                "l2_prefixes": list(spec["l2_prefixes"]),
                "not_pack_entries": True,
            },
            "l1_dcat": {
                "query_id": l1_query["query_id"],
                "query_content_hash": l1_query["query_content_hash"],
                "response_content_hash": l1_query["response_content_hash"],
                "rows": rows,
                "missing_canonical_vars": missing,
                "panel_variable_count": panel_count,
                "nonpanel_variable_count": nonpanel_count,
                "total_observations": sum(int(row["observations"]) for row in rows),
                "total_datasets": sum(int(row["datasets"]) for row in rows),
            },
            "l2_scholar_kg": {
                "query_id": l2_query["query_id"],
                "query_content_hash": l2_query["query_content_hash"],
                "response_content_hash": l2_query["response_content_hash"],
                "owner_query_source_ref": l2_query["owner_query_source_ref"],
                **l2,
            },
            "lever_feasibility": lever_feasibility,
            "transport_feasibility": {
                "owner": "L1 DCAT plus L2 scholar-KG exact variable query",
                "l2_exact_measure_names": sorted(exact_measures),
                "jointly_measured_transport_canonical_vars": transport_vars,
                "jointly_measured_transport_count": len(transport_vars),
            },
            "distinctness_preflight": {
                "outcome_overlap": outcome_overlap,
                "lever_overlap": lever_overlap,
                "method_family": "non_panel" if nonpanel_count else "panel_only",
                "not_ua_single_unit": all(int(row["geographic_units"]) > 1 for row in rows),
                "transport_covariate_check": {
                    "jointly_measured_transport_canonical_vars": transport_vars,
                    "first_vertical_overlap": sorted(
                        set(transport_vars).intersection(
                            set(comparator["transport_covariates"])
                        )
                    ),
                },
            },
        }
    ranking = _rank_candidates(candidates)
    if not ranking:
        raise OwnerDataUnavailableError("domain-selection census has no candidate rows")
    eligible = [item for item in ranking if bool(item["eligible"])]
    chosen_row = (eligible or ranking)[0]
    chosen = str(chosen_row["candidate_id"])
    all_candidates_ineligible = not bool(eligible)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "policy_design_case.gy_n10a.domain_selection_census",
        "rule_version": RULE_VERSION,
        "producer": PRODUCER,
        "query_discipline": {
            "l1": "read_only single aggregate over all candidate canonical vars; parameterized ANY lookup",
            "l2": "read_only single multi-candidate aggregate over canonical owner prefix rows",
            "timing_policy": (
                "E5 timings are retained as operational census metadata, excluded from the "
                "content hash, and preserved by byte-stable rewrites once recorded."
            ),
        },
        "content_hash_excluded_fields": ["runtime_metrics"],
        "runtime_metrics": {
            "query_timings_seconds": dict(sorted(query_timings.items())),
        },
        "owner_paths": {
            "l1_dcat": _repo_relative(paths["l1_dcat"], root),
            "l2_scholar_kg": _repo_relative(paths["l2_skg"], root),
        },
        "first_vertical_comparator": comparator,
        "owner_queries": {
            l1_query["query_id"]: l1_query,
            l2_query["query_id"]: l2_query,
            l2_measure_query["query_id"]: l2_measure_query,
        },
        "candidates": candidates,
        "decision": {
            "ranking": ranking,
            "chosen_candidate": chosen,
            "selection_rationale": (
                f"{chosen} is the highest-scoring "
                + ("eligible" if not all_candidates_ineligible else "best-available ineligible")
                + " candidate under the measured L1/L2/lever/distinctness census."
            ),
            "all_candidates_ineligible": all_candidates_ineligible,
            "ineligible_candidate_gaps": {
                item["candidate_id"]: item["ineligible_reasons"]
                for item in ranking
                if item["ineligible_reasons"]
            },
        },
    }
    return _with_content_hash(
        payload,
        "census_content_hash",
        excluded_fields=("runtime_metrics",),
    )


def _l1_candidate_aggregate(
    path: Path,
    query_timings: dict[str, float],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    all_vars = sorted(
        {item for spec in _CANDIDATE_SPECS.values() for item in spec["l1_canonical_vars"]}
    )
    sql = """
SELECT
  canonical_var,
  COUNT(*) AS observations,
  COUNT(DISTINCT dataset_id) AS datasets,
  COUNT(DISTINCT country_code)
    FILTER (WHERE country_code IS NOT NULL AND country_code <> '') AS geographic_units,
  COUNT(DISTINCT COALESCE(year, survey_year))
    FILTER (WHERE COALESCE(year, survey_year) IS NOT NULL) AS periods,
  MIN(COALESCE(year, survey_year)) AS min_period,
  MAX(COALESCE(year, survey_year)) AS max_period,
  COUNT(*) FILTER (WHERE country_code IS NULL OR country_code = '') AS no_unit_rows,
  COUNT(*) FILTER (WHERE COALESCE(year, survey_year) IS NULL) AS no_period_rows,
  COUNT(DISTINCT json_extract_string(condition_json, '$.unit'))
    FILTER (WHERE json_extract_string(condition_json, '$.unit') IS NOT NULL) AS measurement_unit_values
FROM ds_observations
WHERE canonical_var = ANY(?)
GROUP BY canonical_var
ORDER BY canonical_var
""".strip()
    rows = _run_query(path, "l1_candidate_aggregate", sql, [all_vars], query_timings)
    normalized: list[dict[str, Any]] = []
    for row in rows["rows"]:
        normalized_row = dict(row)
        normalized_row["panel_shape"] = (
            int(normalized_row["geographic_units"]) >= 3
            and int(normalized_row["periods"]) >= 4
        )
        normalized.append(_with_content_hash(normalized_row, "row_content_hash"))
    rows["rows"] = normalized
    rows["response_content_hash"] = _hash(normalized)
    return normalized, rows


def _l2_candidate_aggregate(
    path: Path,
    query_timings: dict[str, float],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidate_prefixes = [
        (candidate_id, prefix)
        for candidate_id, spec in _CANDIDATE_SPECS.items()
        for prefix in spec["l2_prefixes"]
    ]
    candidate_ids = [candidate_id for candidate_id, _ in candidate_prefixes]
    prefixes = [prefix for _, prefix in candidate_prefixes]
    parameters = [candidate_ids, prefixes]
    sql = """
WITH candidate_prefixes AS (
  SELECT
    unnest(?::VARCHAR[]) AS candidate_id,
    unnest(?::VARCHAR[]) AS prefix
),
candidate_ids AS (SELECT DISTINCT candidate_id FROM candidate_prefixes),
matched_variables AS (
  SELECT prefix.candidate_id, variable.canonical_name
  FROM candidate_prefixes AS prefix
  JOIN ac_skg_variables AS variable
    ON lower(COALESCE(variable.canonical_name, '')) LIKE prefix.prefix || '%'
),
matched_claims AS (
  SELECT prefix.candidate_id, claim.id, claim.cause, claim.effect
  FROM candidate_prefixes AS prefix
  JOIN ac_causal_claims AS claim
    ON lower(COALESCE(claim.cause, '')) LIKE prefix.prefix || '%'
    OR lower(COALESCE(claim.effect, '')) LIKE prefix.prefix || '%'
),
matched_parameters AS (
  SELECT prefix.candidate_id, parameter.id
  FROM candidate_prefixes AS prefix
  JOIN ac_parameter_estimates AS parameter
    ON lower(COALESCE(parameter.variable_name, '')) LIKE prefix.prefix || '%'
),
matched_edges AS (
  SELECT prefix.candidate_id, edge.edge_id
  FROM candidate_prefixes AS prefix
  JOIN ac_skg_edges AS edge
    ON lower(COALESCE(edge.src, '')) LIKE prefix.prefix || '%'
    OR lower(COALESCE(edge.dst, '')) LIKE prefix.prefix || '%'
),
variable_counts AS (
  SELECT candidate_id, COUNT(DISTINCT canonical_name) AS variable_count
  FROM matched_variables
  GROUP BY candidate_id
),
claim_counts AS (
  SELECT candidate_id, COUNT(DISTINCT id) AS causal_claim_count,
         COUNT(DISTINCT cause) AS lever_cause_count
  FROM matched_claims
  GROUP BY candidate_id
),
parameter_counts AS (
  SELECT candidate_id, COUNT(DISTINCT id) AS parameter_estimate_count
  FROM matched_parameters
  GROUP BY candidate_id
),
edge_counts AS (
  SELECT candidate_id, COUNT(DISTINCT edge_id) AS edge_count
  FROM matched_edges
  GROUP BY candidate_id
),
transport_counts AS (
  SELECT edge.candidate_id, COUNT(DISTINCT score.transport_id) AS transport_score_count
  FROM matched_edges AS edge
  JOIN ac_skg_transport_scores AS score ON score.edge_id = edge.edge_id
  GROUP BY edge.candidate_id
),
lever_groups AS (
  SELECT prefix.candidate_id, claim.cause, claim.effect,
         COUNT(DISTINCT claim.id) AS claim_count,
         list_sort(list(DISTINCT claim.id)) AS claim_ids
  FROM candidate_prefixes AS prefix
  JOIN ac_causal_claims AS claim
    ON lower(COALESCE(claim.cause, '')) LIKE prefix.prefix || '%'
   AND lower(COALESCE(claim.effect, '')) LIKE prefix.prefix || '%'
  WHERE lower(COALESCE(claim.cause, '')) <> lower(COALESCE(claim.effect, ''))
  GROUP BY prefix.candidate_id, claim.cause, claim.effect
),
ranked_levers AS (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY candidate_id ORDER BY claim_count DESC, cause, effect
  ) AS lever_rank
  FROM lever_groups
)
SELECT
  candidate.candidate_id,
  COALESCE(variable_count, 0) AS variable_count,
  COALESCE(causal_claim_count, 0) AS causal_claim_count,
  COALESCE(lever_cause_count, 0) AS lever_cause_count,
  COALESCE(parameter_estimate_count, 0) AS parameter_estimate_count,
  COALESCE(edge_count, 0) AS edge_count,
  COALESCE(transport_score_count, 0) AS transport_score_count,
  lever_rank,
  cause,
  effect,
  claim_count,
  claim_ids
FROM candidate_ids AS candidate
LEFT JOIN variable_counts USING(candidate_id)
LEFT JOIN claim_counts USING(candidate_id)
LEFT JOIN parameter_counts USING(candidate_id)
LEFT JOIN edge_counts USING(candidate_id)
LEFT JOIN transport_counts USING(candidate_id)
LEFT JOIN ranked_levers USING(candidate_id)
WHERE lever_rank <= 4 OR lever_rank IS NULL
ORDER BY candidate.candidate_id, lever_rank
""".strip()
    query = _run_query(path, "l2_candidate_aggregate", sql, parameters, query_timings)
    grouped: dict[str, dict[str, Any]] = {}
    for row in query["rows"]:
        candidate_id = str(row["candidate_id"])
        group = grouped.setdefault(
            candidate_id,
            {
                "candidate_id": candidate_id,
                "variable_count": int(row["variable_count"]),
                "causal_claim_count": int(row["causal_claim_count"]),
                "lever_cause_count": int(row["lever_cause_count"]),
                "parameter_estimate_count": int(row["parameter_estimate_count"]),
                "edge_count": int(row["edge_count"]),
                "transport_score_count": int(row["transport_score_count"]),
                "top_levers": [],
            },
        )
        if row.get("cause"):
            lever = _with_content_hash(
                {
                    "lever_rank": int(row["lever_rank"]),
                    "cause": str(row["cause"]),
                    "effect": str(row["effect"]),
                    "claim_count": int(row["claim_count"]),
                    "claim_ids": sorted(str(item) for item in row.get("claim_ids") or []),
                },
                "row_content_hash",
            )
            group["top_levers"].append(lever)
    normalized = [grouped[candidate_id] for candidate_id in sorted(grouped)]
    for row in normalized:
        row["top_levers"] = sorted(row["top_levers"], key=lambda item: item["lever_rank"])
        row["row_content_hash"] = _hash(row)
    query["rows"] = normalized
    query["response_content_hash"] = _hash(normalized)
    return normalized, query


def _l2_candidate_measure_names(
    path: Path,
    query_timings: dict[str, float],
) -> tuple[dict[str, tuple[str, ...]], dict[str, Any]]:
    """Measure exact L1/L2 domain-variable overlap in one read-only query."""

    requested: dict[str, list[tuple[str, str]]] = {}
    all_names: set[str] = set()
    for candidate_id, spec in _CANDIDATE_SPECS.items():
        pairs = [
            (canonical_var, f"{prefix}{canonical_var}")
            for canonical_var in spec["l1_canonical_vars"]
            for prefix in spec["l2_prefixes"]
        ]
        requested[candidate_id] = pairs
        all_names.update(name for _, name in pairs)
    sql = """
SELECT canonical_name
FROM ac_skg_variables
WHERE canonical_name = ANY(?)
ORDER BY canonical_name
""".strip()
    query = _run_query(
        path,
        "l2_candidate_exact_measure_names",
        sql,
        [sorted(all_names)],
        query_timings,
    )
    observed_names = {str(row["canonical_name"]) for row in query["rows"]}
    matches = [
        {
            "candidate_id": candidate_id,
            "canonical_var": canonical_var,
            "canonical_name": canonical_name,
        }
        for candidate_id, pairs in sorted(requested.items())
        for canonical_var, canonical_name in pairs
        if canonical_name in observed_names
    ]
    query["rows"] = matches
    query["response_content_hash"] = _hash(matches)
    by_candidate: dict[str, tuple[str, ...]] = {}
    for candidate_id in _CANDIDATE_SPECS:
        by_candidate[candidate_id] = tuple(
            sorted(
                {
                    str(row["canonical_var"])
                    for row in matches
                    if row["candidate_id"] == candidate_id
                }
            )
        )
    return by_candidate, query


def _rank_candidates(candidates: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    def l1_metric(candidate: Mapping[str, Any], key: str) -> float:
        return float(_mapping(candidate.get("l1_dcat")).get(key, 0))

    def l2_metric(candidate: Mapping[str, Any], key: str) -> float:
        return float(_mapping(candidate.get("l2_scholar_kg")).get(key, 0))

    observation_max = max(math.log1p(l1_metric(item, "total_observations")) for item in candidates.values())
    dataset_max = max(math.log1p(l1_metric(item, "total_datasets")) for item in candidates.values())
    nonpanel_max = max(l1_metric(item, "nonpanel_variable_count") for item in candidates.values())
    l2_keys = ("causal_claim_count", "parameter_estimate_count", "transport_score_count")
    l2_max = {
        key: max(math.log1p(l2_metric(item, key)) for item in candidates.values()) for key in l2_keys
    }
    lever_max = max(math.log1p(l2_metric(item, "lever_cause_count")) for item in candidates.values())
    ranking: list[dict[str, Any]] = []
    for candidate_id, candidate in candidates.items():
        l1 = _mapping(candidate.get("l1_dcat"))
        l2 = _mapping(candidate.get("l2_scholar_kg"))
        preflight = _mapping(candidate.get("distinctness_preflight"))
        lever_feasibility = _mapping(candidate.get("lever_feasibility"))
        transport_feasibility = _mapping(candidate.get("transport_feasibility"))
        l1_score = (
            0.50 * _normalized_log(l1.get("total_observations"), observation_max)
            + 0.30 * _normalized_log(l1.get("total_datasets"), dataset_max)
            + 0.20 * _normalized_linear(l1.get("nonpanel_variable_count"), nonpanel_max)
        )
        l2_score = sum(
            _normalized_log(l2.get(key), l2_max[key]) for key in l2_keys
        ) / len(l2_keys)
        lever_abundance_score = _normalized_log(l2.get("lever_cause_count"), lever_max)
        writable_attempts = _list_of_mappings(lever_feasibility.get("l6_writability_attempts"))
        writable_count = int(lever_feasibility.get("l6_positive_writable_count", 0))
        runtime_lever_score = writable_count / max(1, len(writable_attempts))
        lever_score = 0.5 * lever_abundance_score + 0.5 * runtime_lever_score
        transport_score = float(
            int(transport_feasibility.get("jointly_measured_transport_count", 0)) > 0
        )
        distinctness_score = float(
            not _list_of_strings(preflight.get("outcome_overlap"))
            and not _list_of_strings(preflight.get("lever_overlap"))
            and not _list_of_strings(
                _mapping(preflight.get("transport_covariate_check")).get("first_vertical_overlap")
            )
        )
        ineligible_reasons: list[str] = []
        if int(l1.get("nonpanel_variable_count", 0)) == 0:
            ineligible_reasons.append("nonpanel_method_family_absent")
        if _list_of_strings(preflight.get("outcome_overlap")):
            ineligible_reasons.append("first_vertical_outcome_overlap")
        if _list_of_strings(preflight.get("lever_overlap")):
            ineligible_reasons.append("first_vertical_lever_overlap")
        if not bool(preflight.get("not_ua_single_unit")):
            ineligible_reasons.append("insufficient_multi_unit_coverage")
        if int(transport_feasibility.get("jointly_measured_transport_count", 0)) == 0:
            ineligible_reasons.append("domain_transport_covariate_not_jointly_measured")
        if int(l2.get("lever_cause_count", 0)) == 0:
            ineligible_reasons.append("owner_derived_lever_vocabulary_empty")
        eligible = (
            not ineligible_reasons
        )
        score = (
            0.40 * l1_score
            + 0.25 * l2_score
            + 0.15 * lever_score
            + 0.10 * transport_score
            + 0.10 * distinctness_score
        )
        ranking.append(
            {
                "candidate_id": candidate_id,
                "eligible": eligible,
                "score": round(score, 6),
                "score_components": {
                    "l1_outcome_coverage": round(l1_score, 6),
                    "l2_grounding_coverage": round(l2_score, 6),
                    "lever_vocabulary": round(lever_score, 6),
                    "transport_measurement": round(transport_score, 6),
                    "distinctness_preflight": round(distinctness_score, 6),
                },
                "ineligible_reasons": ineligible_reasons,
            }
        )
    return sorted(ranking, key=lambda item: (not item["eligible"], -item["score"], item["candidate_id"]))


def _build_selected_domain_facts(
    root: Path,
    paths: Mapping[str, Path],
    census: Mapping[str, Any],
    query_timings: dict[str, float],
) -> dict[str, Any]:
    chosen = str(_mapping(census.get("decision")).get("chosen_candidate"))
    candidate = _mapping(_mapping(census.get("candidates")).get(chosen))
    l1_rows = _list_of_mappings(_mapping(candidate.get("l1_dcat")).get("rows"))
    l2 = _mapping(candidate.get("l2_scholar_kg"))
    outcome_rows = _select_specific_outcomes(l1_rows)
    exact_l2_names, l2_exact_query = _l2_exact_names(
        paths["l2_skg"],
        [
            f"{prefix}{row['canonical_var']}"
            for row in l1_rows
            for prefix in _CANDIDATE_SPECS[chosen]["l2_prefixes"]
        ],
        query_timings,
    )
    covariate_rows = _select_covariates(
        l1_rows,
        outcome_rows,
        exact_l2_names,
        candidate_id=chosen,
    )
    selected_vars = sorted(
        {str(row["canonical_var"]) for row in [*outcome_rows, *covariate_rows]}
    )
    l1_details, l1_detail_query = _l1_entry_details(
        paths["l1_dcat"], selected_vars, query_timings
    )
    detail_by_var = {str(row["canonical_var"]): row for row in l1_details}
    missing_details = sorted(set(selected_vars).difference(detail_by_var))
    if missing_details:
        raise OwnerDataUnavailableError(
            "selected L1 detail rows missing: " + ", ".join(missing_details)
        )
    profiles, profile_query = _l1_context_profiles(
        paths["l1_dcat"],
        [str(row["canonical_var"]) for row in covariate_rows],
        query_timings,
    )
    source_context, target_context = _select_context_pair(profiles)
    registry = _cached_owner_substrate_registry(root.as_posix())
    l2_query_source_ref = (
        "repo://" + _repo_relative_mounted_evidence_path(paths["l2_skg"], root)
    )
    selected_l2_query_entries = [
        entry
        for entry in registry.entries
        if entry.layer.value == "L2"
        and any(
            ref.split("#", 1)[0] == l2_query_source_ref
            for ref in (*entry.provenance_refs, *entry.authority_refs)
        )
    ]
    if len(selected_l2_query_entries) != 1:
        raise OwnerDataUnavailableError(
            "S0 registry must have exactly one L2 entry resolving the selected query source"
        )
    l6_bundle = load_l6_intervention_substrate(root)
    levers = _list_of_mappings(l2.get("top_levers"))
    if not levers:
        raise OwnerDataUnavailableError("chosen domain has no L2 owner-derived candidate levers")
    writability_attempts = _resolve_l6_writability(l6_bundle, levers)
    l6_entries = [
        {
            "source_id": entry.source_id,
            "family_id": entry.family_id,
            "entry_content_hash": entry.entry_content_hash,
        }
        for entry in registry.entries
        if entry.layer.value == "L6"
    ]
    education_entries = [
        {
            "source_id": entry.source_id,
            "family_id": entry.family_id,
            "layer": entry.layer.value,
            "entry_content_hash": entry.entry_content_hash,
        }
        for entry in registry.entries
        if "education" in entry.source_id.lower() or "education" in entry.family_id.lower()
    ]
    return {
        "chosen_candidate": chosen,
        "outcome_rows": outcome_rows,
        "covariate_rows": covariate_rows,
        "l1_details": detail_by_var,
        "l1_detail_query": l1_detail_query,
        "l2_exact_names": exact_l2_names,
        "l2_exact_query": l2_exact_query,
        "l2_levers": levers,
        "l1_context_profiles": profiles,
        "l1_context_query": profile_query,
        "source_context": source_context,
        "target_context": target_context,
        "s0_registry": {
            "content_hash": registry.content_hash,
            "substrate_version_id": registry.substrate_version_id,
            "registry_payload": registry.model_dump(mode="json"),
            "selected_l2_query_entry_hashes": sorted(
                entry.entry_content_hash for entry in selected_l2_query_entries
            ),
            "selection_evidence": {
                "owner_query_source_ref": l2_query_source_ref,
                "selection_rule": (
                    "registry entry provenance or authority resolves the owner query source"
                ),
            },
            "education_relevant_entries": education_entries,
            "l6_entries": l6_entries,
        },
        "l6_owner": {
            "bundle_content_hash": l6_bundle.content_hash,
            "source_refs": dict(sorted(l6_bundle.source_refs.items())),
            "source_content_hashes": dict(sorted(l6_bundle.source_content_hashes.items())),
            "writability_attempts": writability_attempts,
        },
    }


def _select_specific_outcomes(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    specific = [
        dict(row)
        for row in rows
        if not str(row.get("canonical_var", "")).endswith("_outcomes")
        and "spending" not in str(row.get("canonical_var", ""))
    ]
    panels = sorted(
        (row for row in specific if bool(row.get("panel_shape"))),
        key=lambda row: (-int(row["observations"]), str(row["canonical_var"])),
    )[:2]
    nonpanels = sorted(
        (row for row in specific if not bool(row.get("panel_shape"))),
        key=lambda row: (-int(row["observations"]), str(row["canonical_var"])),
    )[:1]
    if len(panels) < 2 or not nonpanels:
        raise OwnerDataUnavailableError(
            "selected domain lacks required panel and non-panel outcome evidence"
        )
    return [*panels, *nonpanels]


def _select_covariates(
    rows: Sequence[Mapping[str, Any]],
    outcome_rows: Sequence[Mapping[str, Any]],
    exact_l2_names: set[str],
    *,
    candidate_id: str,
) -> list[dict[str, Any]]:
    """Select measured domain transport covariates from census query selectors."""

    outcome_vars = {str(row["canonical_var"]) for row in outcome_rows}
    spec = _CANDIDATE_SPECS[candidate_id]
    prefixes = tuple(str(prefix) for prefix in spec["l2_prefixes"])
    tokens = tuple(str(token) for token in spec["transport_tokens"])
    covariates = [
        dict(row)
        for row in rows
        if str(row.get("canonical_var")) not in outcome_vars
        and any(token in str(row.get("canonical_var", "")) for token in tokens)
        and any(f"{prefix}{row['canonical_var']}" in exact_l2_names for prefix in prefixes)
    ]
    if not covariates:
        raise OwnerDataUnavailableError(
            "no L1/L2 jointly measured domain transport covariate for " + candidate_id
        )
    return sorted(covariates, key=lambda row: str(row["canonical_var"]))


def _l2_exact_names(
    path: Path,
    names: Sequence[str],
    query_timings: dict[str, float],
) -> tuple[set[str], dict[str, Any]]:
    sql = """
SELECT canonical_name
FROM ac_skg_variables
WHERE canonical_name = ANY(?)
ORDER BY canonical_name
""".strip()
    query = _run_query(path, "l2_exact_domain_measure_names", sql, [sorted(names)], query_timings)
    result = {str(row["canonical_name"]) for row in query["rows"]}
    return result, query


def _l1_entry_details(
    path: Path,
    canonical_vars: Sequence[str],
    query_timings: dict[str, float],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sql = """
SELECT
  canonical_var,
  COUNT(*) AS observations,
  COUNT(DISTINCT dataset_id) AS datasets,
  list_sort(list(DISTINCT dataset_id)) AS dataset_ids,
  COUNT(DISTINCT country_code)
    FILTER (WHERE country_code IS NOT NULL AND country_code <> '') AS geographic_units,
  COUNT(DISTINCT COALESCE(year, survey_year))
    FILTER (WHERE COALESCE(year, survey_year) IS NOT NULL) AS periods,
  MIN(COALESCE(year, survey_year)) AS min_period,
  MAX(COALESCE(year, survey_year)) AS max_period,
  COUNT(*) FILTER (WHERE country_code IS NULL OR country_code = '') AS no_unit_rows,
  COUNT(*) FILTER (WHERE COALESCE(year, survey_year) IS NULL) AS no_period_rows
FROM ds_observations
WHERE canonical_var = ANY(?)
GROUP BY canonical_var
ORDER BY canonical_var
""".strip()
    query = _run_query(path, "l1_selected_entry_details", sql, [sorted(canonical_vars)], query_timings)
    normalized = [_with_content_hash(row, "row_content_hash") for row in query["rows"]]
    query["rows"] = normalized
    query["response_content_hash"] = _hash(normalized)
    return normalized, query


def _l1_context_profiles(
    path: Path,
    covariates: Sequence[str],
    query_timings: dict[str, float],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sql = """
SELECT
  country_code,
  canonical_var,
  COUNT(*) AS observations,
  COUNT(DISTINCT COALESCE(year, survey_year)) AS periods,
  MIN(COALESCE(year, survey_year)) AS min_period,
  MAX(COALESCE(year, survey_year)) AS max_period,
  AVG(value) AS mean_value
FROM ds_observations
WHERE canonical_var = ANY(?)
  AND country_code IS NOT NULL
  AND country_code <> ''
GROUP BY country_code, canonical_var
ORDER BY country_code, canonical_var
""".strip()
    query = _run_query(path, "l1_selected_context_profiles", sql, [sorted(covariates)], query_timings)
    normalized = [_with_content_hash(row, "row_content_hash") for row in query["rows"]]
    query["rows"] = normalized
    query["response_content_hash"] = _hash(normalized)
    return normalized, query


def _select_context_pair(rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    by_country: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_country[str(row["country_code"])].append(dict(row))
    candidates = [
        {
            "country_code": country_code,
            "covariates": sorted(country_rows, key=lambda item: str(item["canonical_var"])),
            "coverage_count": len(country_rows),
            "observation_count": sum(int(item["observations"]) for item in country_rows),
        }
        for country_code, country_rows in by_country.items()
    ]
    ranked = sorted(
        candidates,
        key=lambda item: (-item["coverage_count"], -item["observation_count"], item["country_code"]),
    )
    if len(ranked) < 2:
        raise OwnerDataUnavailableError("fewer than two measured country contexts for transport profile")
    return (
        _with_content_hash({"role": "source_candidate", **ranked[0]}, "profile_content_hash"),
        _with_content_hash({"role": "target_candidate", **ranked[1]}, "profile_content_hash"),
    )


def _resolve_l6_writability(bundle: Any, levers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for lever in levers:
        instrument = str(lever["cause"])
        try:
            resolved = resolve_intervention_lever(
                bundle,
                operator_kind=instrument,
                parameter_value=0,
            )
        except InterventionSubstrateError as exc:
            attempts.append(
                _with_content_hash(
                    {
                        "instrument": instrument,
                        "status": "not_owner_writable",
                        "reason_code": exc.code,
                        "owner_bundle_content_hash": bundle.content_hash,
                    },
                    "attempt_content_hash",
                )
            )
            continue
        attempts.append(
            _with_content_hash(
                {
                    "instrument": instrument,
                    "status": "owner_writable",
                    "target_world_slots": list(resolved.target_world_slots),
                    "owner_resolution_hash": resolved.content_hash,
                    "owner_bundle_content_hash": bundle.content_hash,
                },
                "attempt_content_hash",
            )
        )
    return attempts


def _census_lever_feasibility(
    *,
    candidate_id: str,
    top_levers: Sequence[Mapping[str, Any]],
    registry: Any,
    l6_bundle: Any,
    cg3_application_scope: str,
) -> dict[str, Any]:
    """Measure S0/L6/CG3 free-grow feasibility without adding a registry entry."""

    prefixes = tuple(
        str(prefix).removesuffix(".")
        for prefix in _CANDIDATE_SPECS[candidate_id]["l2_prefixes"]
    )
    matching_s0_entries = [
        {
            "source_id": entry.source_id,
            "family_id": entry.family_id,
            "layer": entry.layer.value,
            "entry_content_hash": entry.entry_content_hash,
        }
        for entry in registry.entries
        if any(
            prefix in entry.source_id.lower() or prefix in entry.family_id.lower()
            for prefix in prefixes
        )
    ]
    attempts = _resolve_l6_writability(l6_bundle, top_levers)
    positive_count = sum(item.get("status") == "owner_writable" for item in attempts)
    return {
        "s0_registry_content_hash": registry.content_hash,
        "s0_matching_entry_count": len(matching_s0_entries),
        "s0_matching_entries": matching_s0_entries,
        "l6_bundle_content_hash": l6_bundle.content_hash,
        "l6_writability_attempts": attempts,
        "l6_positive_writable_count": positive_count,
        "cg3_application_scope": cg3_application_scope,
        "durable_s0_registration_available": False,
        "durable_registration_reason": (
            "cg3_shadow_only_and_no_live_second_domain_s0_writer"
            if "shadow_until_live" in cg3_application_scope
            else "live_s0_writer_status_not_owner_proven"
        ),
    }


def _preferred_lever(levers: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Choose one already-owner-derived lever deterministically for live probes."""

    if not levers:
        raise OwnerDataUnavailableError("chosen domain has no L2 owner-derived candidate levers")
    return next(
        (dict(item) for item in levers if "outcomes" in str(item.get("effect", ""))),
        dict(levers[0]),
    )


def _n7_capture_now() -> datetime:
    """Return the actual UTC capture time for one live N7 owner call."""

    return datetime.now(UTC)


def _n7_attempt_input_content_hash(facts: Mapping[str, Any]) -> str:
    """Bind one N7 owner receipt to the inputs that selected its live attempt."""

    selected = _preferred_lever(_list_of_mappings(facts.get("l2_levers")))
    outcome = _list_of_mappings(facts.get("outcome_rows"))[0]
    registry = _mapping(facts.get("s0_registry"))
    return _n7_attempt_input_binding_hash(
        attempted_variable=selected.get("cause"),
        source_l2_row_content_hash=selected.get("row_content_hash"),
        owner_l2_effect=selected.get("effect"),
        outcome_min_period=outcome.get("min_period"),
        outcome_max_period=outcome.get("max_period"),
        substrate_registry_content_hash=registry.get("content_hash"),
        substrate_version_id=registry.get("substrate_version_id"),
        effective_owner_config=_n7_effective_owner_config(),
    )


def _n7_attempt_input_binding_hash(
    *,
    attempted_variable: Any,
    source_l2_row_content_hash: Any,
    owner_l2_effect: Any,
    outcome_min_period: Any,
    outcome_max_period: Any,
    substrate_registry_content_hash: Any,
    substrate_version_id: Any,
    effective_owner_config: Mapping[str, Any],
) -> str:
    """Hash the exact owner inputs that select one cached N7 attempt."""

    return _hash(
        {
            "attempted_variable": attempted_variable,
            "attempt_source_l2_row_content_hash": source_l2_row_content_hash,
            "owner_l2_effect": owner_l2_effect,
            "observation_window": {
                "min_period": outcome_min_period,
                "max_period": outcome_max_period,
            },
            "substrate_registry_content_hash": substrate_registry_content_hash,
            "substrate_version_id": substrate_version_id,
            "effective_owner_config": dict(effective_owner_config),
        }
    )


def _n7_effective_owner_config() -> dict[str, Any]:
    """Resolve the canonical Fabric retrieval limits that produced the receipt."""

    from polisyos.core.contracts.control import DataResolveRequest
    from polisyos.fabric.retrieval.explore_lane import ExploreLaneLimits

    limits = ExploreLaneLimits()
    return {
        "receipt_proof_head_commit": N10A_PROOF_HEAD_COMMIT,
        "owner_gateway": "runtime.quality.acquisition_planner.RealAcquisitionOwnerGateway",
        "owner_endpoint": "RetrievalService.resolve",
        "request_mode": "hybrid",
        "allow_explore_fallback": bool(
            DataResolveRequest.model_fields["allow_explore_fallback"].default
        ),
        "explore_limits": {
            "max_sources_per_query": limits.max_sources_per_query,
            "max_discovery_calls_per_source": limits.max_discovery_calls_per_source,
            "max_candidates_total": limits.max_candidates_total,
            "time_budget_ms": limits.time_budget_ms,
            "cost_budget_usd": limits.cost_budget_usd,
        },
        "feature_flag_environment": {
            "POLISYOS_RETRIEVAL_FASTLANE_ENABLED": os.environ.get(
                "POLISYOS_RETRIEVAL_FASTLANE_ENABLED",
                "<default:true>",
            ),
            "POLISYOS_RETRIEVAL_EXPLORE_ENABLED": os.environ.get(
                "POLISYOS_RETRIEVAL_EXPLORE_ENABLED",
                "<default:true>",
            ),
        },
    }


def _n7_attempt_input_content_hash_from_pack(pack: Mapping[str, Any]) -> str:
    """Recompute the N7 E1 cache key from owner-derived pack projections."""

    attempt = _mapping(pack.get("n7_acquisition"))
    components = _mapping(pack.get("components"))
    instrument = str(attempt.get("attempted_variable") or "")
    levers = [
        lever
        for lever in _list_of_mappings(
            _mapping(components.get("lever_vocabulary")).get("entries")
        )
        if str(lever.get("instrument") or "") == instrument
    ]
    outcomes = _list_of_mappings(_mapping(components.get("outcomes")).get("entries"))
    if len(levers) != 1 or not outcomes:
        raise ValueError("n7_attempt_input_owner_projection_unresolved")
    lever = levers[0]
    lever_evidence = _mapping(lever.get("owner_evidence"))
    if lever_evidence.get("source_row_content_hash") != attempt.get(
        "attempt_source_l2_row_content_hash"
    ):
        raise ValueError("n7_attempt_input_lever_evidence_mismatch")
    outcome = outcomes[0]
    registry = _mapping(components.get("substrate_registry"))
    effective_owner_config = _mapping(attempt.get("attempt_effective_owner_config"))
    if effective_owner_config != _n7_effective_owner_config():
        raise ValueError("n7_attempt_effective_owner_config_mismatch")
    return _n7_attempt_input_binding_hash(
        attempted_variable=instrument,
        source_l2_row_content_hash=lever_evidence.get("source_row_content_hash"),
        owner_l2_effect=lever.get("target_concept"),
        outcome_min_period=outcome.get("min_period"),
        outcome_max_period=outcome.get("max_period"),
        substrate_registry_content_hash=registry.get("content_hash"),
        substrate_version_id=registry.get("substrate_version_id"),
        effective_owner_config=effective_owner_config,
    )


def _load_historical_n7_attempt(
    root: Path,
    facts: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Reuse the immutable proof-head N7 owner receipt when current inputs match."""

    try:
        frozen_pack = _historical_n10a_pack_payload(root)
    except RuntimeError:
        return None
    attempt = copy.deepcopy(_mapping(frozen_pack.get("n7_acquisition")))
    historical_operational = copy.deepcopy(
        _mapping(_mapping(frozen_pack.get("runtime_metrics")).get("n7_acquisition"))
    )
    historical_receipt_payload = _mapping(historical_operational.get("receipt"))
    if not historical_receipt_payload:
        return None
    operational = _n7_operational_metadata(historical_receipt_payload)
    selected = _preferred_lever(_list_of_mappings(facts.get("l2_levers")))
    expected_input_hash = _n7_attempt_input_content_hash(facts)
    if (
        attempt.get("attempted_variable") != selected.get("cause")
        or attempt.get("attempt_source_l2_row_content_hash")
        != selected.get("row_content_hash")
    ):
        return None
    receipt_content = _mapping(attempt.get("receipt_content"))
    compiled_specs = _list_of_mappings(receipt_content.get("compiled_requirement_specs"))
    expected_world_ref = (
        "s0://substrate-registry/"
        + str(_mapping(facts.get("s0_registry")).get("substrate_version_id"))
    )
    compute_economics = _mapping(receipt_content.get("compute_economics"))
    if (
        len(compiled_specs) != 1
        or compiled_specs[0].get("required_data_families") != [selected.get("cause")]
        or compiled_specs[0].get("concept_spine_refs")
        != [f"skg:{selected.get('row_content_hash')}"]
        or compute_economics.get("cached_world_ref_reused") != expected_world_ref
    ):
        return None
    attempt["attempt_input_content_hash"] = expected_input_hash
    attempt["attempt_effective_owner_config"] = _n7_effective_owner_config()
    attempt.pop("gap_refs", None)
    validation_issues: list[dict[str, Any]] = []
    _validate_n7_receipt_evidence(attempt, operational, validation_issues)
    if validation_issues:
        return None
    attempt["runtime_metrics"] = operational
    return attempt


def _run_n7_live_attempt(root: Path, facts: Mapping[str, Any]) -> dict[str, Any]:
    """Run one real-owner N7 attempt and retain its journal-first receipt.

    The receipt is evidence about the existing N7 seam, not an authority source
    for a pack entry. In particular, an N7 registration must still rederive its
    fields from a measured owner response before it can reach S0/L6.
    """

    selected = _preferred_lever(_list_of_mappings(facts.get("l2_levers")))
    instrument = str(selected["cause"])
    outcome = _list_of_mappings(facts.get("outcome_rows"))[0]
    requirement_id = f"data-requirement:gy-n10a:{_identifier(instrument)}"
    spec = DataRequirementSpec(
        requirement_id=requirement_id,
        claim_id=f"claim:gy-n10a:{_identifier(instrument)}",
        claim_family="education_intervention",
        claim_type="causal_intervention",
        claim_use="grounding_acquisition_probe",
        required_data_families=(instrument,),
        scope=DataRequirementScope(
            population="learners",
            geography="cross_country",
            time=f"{outcome['min_period']}-{outcome['max_period']}",
            time_role="observation_time",
        ),
        recency_horizon="P90D",
        lineage_strictness="strict",
        quality_minima=DataQualityMinimums(min_quality_score=0.8, min_completeness=0.95),
        missingness_tolerance=0.02,
        transformation_tolerance="none",
        admissibility_predicates=("source_family_matches_compiled_requirement",),
        mandatory_facets=("source_contract_ref", "lineage_refs"),
        concept_spine_refs=(f"skg:{selected['row_content_hash']}",),
        authority_profile_refs=("authority_profile.research",),
        source_requirement_refs=(f"l2:{selected['row_content_hash']}",),
        metadata={
            "attempt_kind": "gy_n10a_one_live_variable_probe",
            "owner_l2_cause": instrument,
            "owner_l2_effect": str(selected["effect"]),
        },
    )
    world = AcquisitionWorldSnapshot(
        world_ref=(
            "s0://substrate-registry/"
            + str(_mapping(facts.get("s0_registry")).get("substrate_version_id"))
        ),
        known_slots=(instrument,),
        dependency_index={instrument: ("design:gy-n10a-education-acquisition",)},
        design_revalidation_stages={
            "design:gy-n10a-education-acquisition": ("grounding", "value_set")
        },
        substrate_registry=_mapping(_mapping(facts.get("s0_registry")).get("registry_payload")),
        world_model_record_ref="world-model:gy-n10a-education-acquisition",
    )
    capture_time = _n7_capture_now()
    receipt = run_acquisition_closed_loop(
        run_id="gy-n10a-education-one-variable-n7",
        acquisition_request={
            "request_kind": "owner_grounding_evidence",
            "driver": "gy_n10a_free_grow_probe",
            "counterexample_ref": f"l2:{selected['row_content_hash']}",
            "cycle_index": 0,
            "consumer_owner": PRODUCER,
            "reentry": "same_generation_cycle_index",
        },
        data_requirement_specs=(spec,),
        world_snapshot=world,
        owner_gateway=RealAcquisitionOwnerGateway(repo_root=root, captured_at=capture_time),
        useful_design_rate_before=0.0,
        generated_at=capture_time,
    )
    receipt_payload = receipt.model_dump(mode="json")
    receipt_content = _n7_owner_evidence_projection(receipt_payload)
    owner_artifacts = _list_of_mappings(receipt_payload.get("owner_artifacts"))
    raw_response_checks = [
        {
            "artifact_ref": artifact.get("artifact_ref"),
            "raw_response_hash": _mapping(artifact.get("payload")).get(
                "raw_owner_response_hash"
            ),
            "recomputed_raw_response_hash": _n7_owner_response_hash(
                _mapping(_mapping(artifact.get("payload")).get("owner_response"))
            ),
        }
        for artifact in owner_artifacts
    ]
    for check in raw_response_checks:
        check["matches"] = check["raw_response_hash"] == check["recomputed_raw_response_hash"]
    rejection_reason = _n7_pack_entry_rejection_reason(owner_artifacts)
    receipt_issues = list(validate_acquisition_receipt(receipt))
    receipt_is_rederivable = (
        not receipt_issues
        and receipt.compiled_spec_count == 1
        and len(owner_artifacts) == 1
        and len(receipt.journal_entries) == 1
        and all(bool(row["matches"]) for row in raw_response_checks)
    )
    return {
        "receipt_count": 1,
        "attempt_input_content_hash": _n7_attempt_input_content_hash(facts),
        "attempt_effective_owner_config": _n7_effective_owner_config(),
        "attempt_status": receipt.status,
        "attempted_variable": instrument,
        "attempt_source_l2_row_content_hash": selected["row_content_hash"],
        "one_live_variable_per_attempt": True,
        "receipt_content": receipt_content,
        "receipt_content_hash": _n7_owner_evidence_hash(receipt_payload),
        "owner_rederive_status": "pass" if receipt_is_rederivable else "fail",
        "receipt_validation_issues": receipt_issues,
        "raw_response_hash_checks": raw_response_checks,
        "pack_entry_eligible": False,
        "pack_entry_rejection_reason": rejection_reason,
        "journal_persistence_status": "receipt_embedded_in_content_addressed_pack_manifest",
        "runtime_metrics": _n7_operational_metadata(receipt_payload),
    }


def _n7_owner_response_hash(response: Mapping[str, Any]) -> str:
    """Recompute N7's raw-owner-response hash without trusting the receipt field."""

    encoded = json.dumps(
        dict(response), sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _n7_owner_evidence_projection(receipt_payload: Mapping[str, Any]) -> dict[str, Any]:
    """Project an N7 receipt into content-bound owner facts without run timing."""

    projection = copy.deepcopy(_json_value(dict(receipt_payload)))
    projection.pop("content_hash", None)
    projection.pop("generated_at", None)
    planner_report = _mapping(projection.get("planner_report"))
    planner_report.pop("generated_at", None)
    projection["planner_report"] = planner_report
    owner_artifacts = _list_of_mappings(projection.get("owner_artifacts"))
    for artifact in owner_artifacts:
        capture_provenance = _mapping(artifact.get("capture_provenance"))
        capture_provenance.pop("captured_at", None)
        artifact["capture_provenance"] = capture_provenance
    projection["owner_artifacts"] = owner_artifacts
    return projection


def _n7_owner_evidence_hash(receipt_payload: Mapping[str, Any]) -> str:
    """Hash the time-free N7 owner-evidence projection used by the pack."""

    return _hash(_n7_owner_evidence_projection(receipt_payload))


def _n7_content_time_paths(value: Mapping[str, Any]) -> list[str]:
    """Return known N7 operational receipt paths that leaked into content evidence."""

    paths: list[str] = []
    if "generated_at" in value:
        paths.append("generated_at")
    planner_report = _mapping(value.get("planner_report"))
    if "generated_at" in planner_report:
        paths.append("planner_report.generated_at")
    for index, artifact in enumerate(_list_of_mappings(value.get("owner_artifacts"))):
        capture_provenance = _mapping(artifact.get("capture_provenance"))
        if "captured_at" in capture_provenance:
            paths.append(f"owner_artifacts[{index}].capture_provenance.captured_at")
    return paths


def _n7_operational_metadata(receipt_payload: Mapping[str, Any]) -> dict[str, Any]:
    """Retain only N7 timing fields, never a second unhashed receipt copy."""

    artifacts = _list_of_mappings(receipt_payload.get("owner_artifacts"))
    return {
        "receipt_generated_at": receipt_payload.get("generated_at"),
        "planner_report_generated_at": _mapping(receipt_payload.get("planner_report")).get(
            "generated_at"
        ),
        "owner_capture_times": [
            _mapping(artifact.get("capture_provenance")).get("captured_at")
            for artifact in artifacts
        ],
    }


def _reconstruct_n7_receipt_payload(
    receipt_content: Mapping[str, Any], operational: Mapping[str, Any]
) -> dict[str, Any]:
    """Rejoin static owner evidence and run timing for transient engine validation."""

    payload = copy.deepcopy(_json_value(dict(receipt_content)))
    generated_at = operational.get("receipt_generated_at")
    planner_generated_at = operational.get("planner_report_generated_at")
    capture_times = operational.get("owner_capture_times")
    if not generated_at or not planner_generated_at or not isinstance(capture_times, list):
        raise ValueError("n7_operational_capture_metadata_missing")
    artifacts = _list_of_mappings(payload.get("owner_artifacts"))
    if len(capture_times) != len(artifacts) or any(not value for value in capture_times):
        raise ValueError("n7_operational_capture_metadata_missing")
    payload["generated_at"] = generated_at
    planner_report = _mapping(payload.get("planner_report"))
    planner_report["generated_at"] = planner_generated_at
    payload["planner_report"] = planner_report
    for artifact, captured_at in zip(artifacts, capture_times, strict=True):
        capture_provenance = _mapping(artifact.get("capture_provenance"))
        capture_provenance["captured_at"] = captured_at
        artifact["capture_provenance"] = capture_provenance
    payload["owner_artifacts"] = artifacts
    payload.pop("content_hash", None)
    return payload


def _n7_pack_entry_rejection_reason(owner_artifacts: Sequence[Mapping[str, Any]]) -> str:
    """Derive why a real N7 receipt still cannot become a pack registration."""

    registrations = [
        registration
        for artifact in owner_artifacts
        for registration in _list_of_mappings(
            _mapping(artifact.get("payload")).get("acquired_substrate_registrations")
        )
    ]
    if not registrations:
        return "n7_owner_response_has_no_owner_derived_registration"
    if any(str(item.get("source_id", "")).startswith("fabric.") for item in registrations):
        return "n7_registration_projection_not_owner_measure_derived"
    return "n7_registration_owner_measure_rederivation_unproven"


def _build_smoke_problem(census: Mapping[str, Any], facts: Mapping[str, Any]) -> dict[str, Any]:
    selected = _preferred_lever(_list_of_mappings(facts.get("l2_levers")))
    nonpanel_outcome = next(
        row for row in _list_of_mappings(facts.get("outcome_rows")) if not bool(row.get("panel_shape"))
    )
    lever_id = _identifier(str(selected["cause"]))
    target_slot = _identifier(str(selected["effect"]))
    problem = DesignProblem(
        design_problem_id="education_second_domain_smoke",
        problem_statement=(
            "Improve education outcomes through owner-derived intervention concepts without "
            "claiming unsupported world-slot writability or promotion authority."
        ),
        domain=str(facts["chosen_candidate"]),
        nl_provenance=NLProvenance(
            raw_request="Improve education outcomes through evidence-backed interventions.",
            source_surface="gy_n10a_second_domain_pack",
            source_context={"census_content_hash": census["census_content_hash"]},
        ),
        authority_profile=AuthorityProfile(
            requester_authority="research_lab",
            requested_authority_level="research",
            mandate="GY-N10a cycle-entry smoke only; no promotion authority.",
            authority_refs=["architecture/policy_design_case/layer3_gy_second_domain_pack.json"],
        ),
        jurisdiction_time=JurisdictionTimeSemantics(
            region="cross_country",
            valid_time="2022",
            as_of="2026-07-09",
            policy_time="2022",
            data_time="2022",
        ),
        objectives=[
            DesignObjective(
                objective_id="improve_education_outcomes",
                description="Improve measured education outcomes.",
                metric_id=str(nonpanel_outcome["canonical_var"]),
            )
        ],
        constraints=[
            DesignConstraint(
                constraint_id="no_unverified_promotion",
                description="No candidate may promote without verified grounding and value evidence.",
                hard=True,
                admissibility_basis="request_text",
                source_text="Do not promote unverified candidates.",
            )
        ],
        stakeholders=[
            DesignStakeholder(
                stakeholder_id="learners",
                name="Learners",
                role="affected_population",
            )
        ],
        outcome_of_interest=OutcomeOfInterest(
            target_variable=str(nonpanel_outcome["canonical_var"]),
            metric_id=str(nonpanel_outcome["canonical_var"]),
            estimand="average_treatment_effect",
        ),
        candidate_lever_space=CandidateLeverSpace(
            allowed_operator_kinds=["candidate_intervention"],
            candidate_levers=[
                CandidateLever(
                    lever_id=lever_id,
                    operator_kind="candidate_intervention",
                    instrument=str(selected["cause"]),
                    target_slot=target_slot,
                )
            ],
        ),
        evidence_acquisition_needs=EvidenceAcquisitionNeeds(
            needs=[
                EvidenceNeed(
                    need_id="education_grounding",
                    question="Which owner-derived evidence binds this education intervention?",
                    required_for="A-side grounding",
                    status="required",
                    source_hint="L2 scholar knowledge graph",
                    artifact_ref=f"sha256:{str(selected['row_content_hash']).removeprefix('sha256:')}",
                )
            ]
        ),
        runtime_hints={"generation_cycle_grammar": ("seed",)},
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "policy_design_case.gy_n10a.smoke_design_problem",
        "rule_version": RULE_VERSION,
        "producer": PRODUCER,
        "lever_owner_evidence": {
            "l2_query_id": _mapping(_mapping(census["candidates"])[facts["chosen_candidate"]]).get(
                "l2_scholar_kg", {}
            ).get("query_id"),
            "lever_row_content_hash": selected["row_content_hash"],
            "target_slot_status": "candidate_unbound_world_slot",
        },
        "design_problem": problem.model_dump(mode="json"),
    }
    return _with_content_hash(payload, "smoke_problem_content_hash")


def _build_cycle_trace(root: Path, smoke_problem: Mapping[str, Any]) -> dict[str, Any]:
    problem = DesignProblem.model_validate(smoke_problem["design_problem"])

    async def run() -> Any:
        controller = GenerationCycleController(
            generation_port=_UnavailableOwnerGenerationPort(),
            repo_root=root,
        )
        return await controller.run(
            problem,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            min_cycles=2,
            max_cycles=1,
        )

    run_result = asyncio.run(run())
    raw_run_payload = run_result.model_dump(mode="json")
    run_payload, runtime_metrics = _normalize_n6_run_payload(raw_run_payload)
    normalized_run = GenerationCycleRun.model_validate(run_payload)
    validation_issues = list(validate_generation_cycle_run(normalized_run))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "policy_design_case.gy_n10a.cycle_entry_trace",
        "rule_version": RULE_VERSION,
        "producer": PRODUCER,
        "smoke_problem_content_hash": smoke_problem["smoke_problem_content_hash"],
        "generation_owner_status": "unavailable_then_real_n6_grammar_fallback",
        "execution_status": "completed",
        "smoke_status": "typed_terminal_with_known_n6_validation_gap",
        "content_hash_excluded_fields": ["runtime_metrics"],
        "runtime_metrics": runtime_metrics,
        "generation_cycle_run": run_payload,
        "n6_validation_issues": validation_issues,
        "known_runtime_gap": {
            "code": "n6_single_terminal_validation_gap",
            "present": any(
                str(issue.get("code")) == "positive_cycle_denominator_missing"
                for issue in validation_issues
            ),
        },
    }
    return _with_content_hash(
        payload,
        "trace_content_hash",
        excluded_fields=("runtime_metrics",),
    )


def _normalize_n6_run_payload(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Separate nondeterministic N6 elapsed time from the replay-visible trace."""

    normalized = copy.deepcopy(dict(payload))
    cycle_metrics: list[dict[str, Any]] = []
    cycles = _list_of_mappings(normalized.get("cycles"))
    for index, cycle in enumerate(cycles):
        value_port = _mapping(cycle.get("value_port"))
        if "wall_time_ms" in value_port:
            cycle_metrics.append(
                {"cycle_index": index, "value_port_wall_time_ms": value_port["wall_time_ms"]}
            )
            value_port["wall_time_ms"] = 0.0
            cycle["value_port"] = value_port
    normalized["cycles"] = cycles
    top_level_value_port = _mapping(normalized.get("value_port"))
    top_level_metric = top_level_value_port.get("wall_time_ms")
    if "wall_time_ms" in top_level_value_port:
        top_level_value_port["wall_time_ms"] = 0.0
        normalized["value_port"] = top_level_value_port
    return normalized, {
        "cycle_value_port_wall_time_ms": cycle_metrics,
        "aggregate_value_port_wall_time_ms": top_level_metric,
    }


def _build_gap_report(
    root: Path,
    facts: Mapping[str, Any],
    cycle_trace: Mapping[str, Any],
) -> dict[str, Any]:
    seam_witnesses = {
        gap_id: _resolve_gap_witness(root, spec)
        for gap_id, spec in GAP_WITNESS_SPECS.items()
    }
    positive_writable = [
        row
        for row in _list_of_mappings(_mapping(facts.get("l6_owner")).get("writability_attempts"))
        if row.get("status") == "owner_writable"
    ]
    n7_attempt = _mapping(facts.get("n7_attempt"))
    registration_witness = seam_witnesses["owner_registration_derivation_missing"]
    n8_comparator = _first_vertical_comparator(root)
    gaps = [
        {
            "gap_id": "s0_to_l6_world_slot_bridge_missing",
            "capability_label": "bridge_missing",
            "blocking_seam": "L2 candidate intervention concepts do not resolve through the real L6 knob owner.",
            "owner_evidence": {
                "l6_bundle_content_hash": _mapping(facts.get("l6_owner")).get("bundle_content_hash"),
                "writability_attempts": _mapping(facts.get("l6_owner")).get("writability_attempts"),
                "positive_writable_count": len(positive_writable),
                "seam_witness": seam_witnesses["s0_to_l6_world_slot_bridge_missing"],
            },
            "acquisition_required": {
                "status": "unrunnable_without_engine_bridge",
                "cost_usd": None,
                "cost_basis": "N7 has no owner-derived L2/L3-to-L6 world-slot capture route.",
            },
        },
        {
            "gap_id": "owner_registration_derivation_missing",
            "capability_label": "artifact_missing",
            "blocking_seam": (
                "N7's real owner receipt is journaled, but its projected registration is not "
                "rederived from the captured domain-owner measurements."
            ),
            "owner_evidence": {
                "seam_witness": registration_witness,
                "direct_persist_substrate_registry_call": (
                    "persist_substrate_registry"
                    in registration_witness["observed_call_names"]
                ),
                "direct_persist_acquisition_receipt_call": (
                    "persist_acquisition_receipt"
                    in registration_witness["observed_call_names"]
                ),
                "live_n7_receipt_content_hash": n7_attempt.get("receipt_content_hash"),
                "live_n7_attempt_status": n7_attempt.get("attempt_status"),
                "live_n7_pack_entry_rejection_reason": n7_attempt.get(
                    "pack_entry_rejection_reason"
                ),
                "live_n7_raw_response_hash_checks": n7_attempt.get(
                    "raw_response_hash_checks"
                ),
            },
            "acquisition_required": {
                "status": "unrunnable_without_owner_capture_persistence",
                "cost_usd": None,
                "cost_basis": "No N7 owner endpoint rederives registration measures from L2/L3 rows.",
            },
        },
        {
            "gap_id": "journal_raw_evidence_persistence_missing",
            "capability_label": "artifact_missing",
            "blocking_seam": (
                "The live N7 receipt carries a journal-first entry and raw-response hash, but "
                "the existing owner exposes no durable journal/CAS artifact for later S0/L6 use."
            ),
            "owner_evidence": {
                "receipt_content_hash": n7_attempt.get("receipt_content_hash"),
                "journal_persistence_status": n7_attempt.get("journal_persistence_status"),
                "journal_entries": _mapping(n7_attempt.get("receipt_content")).get(
                    "journal_entries"
                ),
                "seam_witness": seam_witnesses["journal_raw_evidence_persistence_missing"],
            },
        },
        {
            "gap_id": "s0_to_n4_l6_bridge_missing",
            "capability_label": "consumer_missing",
            "blocking_seam": "N4 loads its fixed L6 substrate instead of a persisted second-domain S0 entry.",
            "owner_evidence": {
                "seam_witness": seam_witnesses["s0_to_n4_l6_bridge_missing"],
            },
        },
        {
            "gap_id": "s0_to_n5_wmr_bridge_missing",
            "capability_label": "consumer_missing",
            "blocking_seam": "Default N6/N5 rebuilds the boundary registry and remains first-vertical scoped.",
            "owner_evidence": {
                "seam_witness": seam_witnesses["s0_to_n5_wmr_bridge_missing"],
            },
        },
        {
            "gap_id": "n8_transport_tuple_hardcode",
            "capability_label": "consumer_missing",
            "blocking_seam": "N8 still consumes first-vertical transport covariates rather than pack data.",
            "owner_evidence": {
                "first_vertical_transport_covariates": n8_comparator["transport_covariates"],
                "first_vertical_method_family": n8_comparator["method_family"],
                "seam_witness": seam_witnesses["n8_transport_tuple_hardcode"],
            },
        },
        {
            "gap_id": "n6_single_terminal_validation_gap",
            "capability_label": "semantic_test_missing",
            "blocking_seam": "A typed one-cycle terminal reaches N6 but its validator requires a positive two-cycle denominator.",
            "owner_evidence": {
                "trace_content_hash": cycle_trace["trace_content_hash"],
                "n6_validation_issues": cycle_trace["n6_validation_issues"],
                "seam_witness": seam_witnesses["n6_single_terminal_validation_gap"],
            },
        },
    ]
    hashed = [_with_content_hash(gap, "gap_content_hash") for gap in gaps]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "policy_design_case.gy_n10a.free_grow_gap_report",
        "rule_version": RULE_VERSION,
        "producer": PRODUCER,
        "status": "gaps_recorded_no_engine_change",
        "gaps": hashed,
    }
    return _with_content_hash(payload, "gap_report_content_hash")


def second_domain_substrate_input_content_hash(pack: Mapping[str, Any]) -> str:
    """Hash only stable owner inputs available before cycle/gap production."""

    components = _mapping(pack.get("components"))
    owner_queries = _mapping(pack.get("owner_query_results"))
    registry = _mapping(components.get("substrate_registry"))
    writability = _mapping(components.get("owner_writability"))
    transport = _mapping(components.get("transport_context"))
    query_bindings = {}
    for query_id in (
        "l1_selected_entry_details",
        "l2_selected_levers",
        "l2_exact_domain_measure_names",
        "l1_selected_context_profiles",
    ):
        query = _mapping(owner_queries.get(query_id))
        query_bindings[query_id] = {
            "query_id": query.get("query_id"),
            "query_content_hash": query.get("query_content_hash"),
            "response_content_hash": query.get("response_content_hash"),
        }
    return _hash(
        {
            "selected_domain": pack.get("selected_domain"),
            "substrate_registry": {
                "content_hash": registry.get("content_hash"),
                "substrate_version_id": registry.get("substrate_version_id"),
                "selected_entry_hashes": sorted(
                    _list_of_strings(registry.get("selected_entry_hashes"))
                ),
                "selection_evidence": registry.get("selection_evidence"),
            },
            "lever_entries": _list_of_mappings(
                _mapping(components.get("lever_vocabulary")).get("entries")
            ),
            "outcome_entries": _list_of_mappings(
                _mapping(components.get("outcomes")).get("entries")
            ),
            "transport_context": {
                "status": transport.get("status"),
                "covariates": _list_of_mappings(transport.get("covariates")),
                "source_context": _mapping(transport.get("source_context")),
                "target_context": _mapping(transport.get("target_context")),
            },
            "l6_owner": {
                "bundle_content_hash": writability.get("l6_bundle_content_hash"),
                "attempts": _list_of_mappings(writability.get("attempts")),
            },
            "owner_query_bindings": query_bindings,
        }
    )


def _build_cycle_substrate_input_projection(
    census: Mapping[str, Any],
    facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Assemble the stable owner projection before any cycle or gap runs."""

    chosen = str(facts["chosen_candidate"])
    l1_detail_query = _mapping(facts.get("l1_detail_query"))
    detail_rows = _mapping(facts.get("l1_details"))
    outcome_entries = [
        _pack_l1_entry(
            detail_rows[str(row["canonical_var"])],
            "outcome",
            l1_detail_query,
        )
        for row in _list_of_mappings(facts.get("outcome_rows"))
    ]
    covariate_entries = [
        _pack_l1_entry(
            detail_rows[str(row["canonical_var"])],
            "transport_covariate",
            l1_detail_query,
        )
        for row in _list_of_mappings(facts.get("covariate_rows"))
    ]
    l2_component = _mapping(
        _mapping(census["candidates"])[chosen].get("l2_scholar_kg")
    )
    selected_registry_hashes = _list_of_strings(
        _mapping(facts.get("s0_registry")).get("selected_l2_query_entry_hashes")
    )
    if len(selected_registry_hashes) != 1:
        raise OwnerDataUnavailableError(
            "cycle substrate intake requires exactly one selected L2 registry entry"
        )
    lever_entries = [
        _pack_l2_lever_entry(
            row,
            l2_component,
            selected_registry_entry_hash=selected_registry_hashes[0],
        )
        for row in _list_of_mappings(facts.get("l2_levers"))
    ]
    attempts = _list_of_mappings(
        _mapping(facts.get("l6_owner")).get("writability_attempts")
    )
    writable = [item for item in attempts if item.get("status") == "owner_writable"]
    payload = {
        "selected_domain": chosen,
        "components": {
            "outcomes": {
                "owner": "L1 DCAT ds_observations",
                "selection_rule": (
                    "two highest-observation specific panel outcomes plus one "
                    "highest-observation non-panel outcome"
                ),
                "entries": outcome_entries,
            },
            "lever_vocabulary": {
                "owner": "L2 scholar knowledge graph ac_causal_claims",
                "selection_rule": (
                    "top owner causal cause/effect groups ranked by claim count"
                ),
                "entries": lever_entries,
                "s0_registration_status": "bridge_missing_no_new_registry_format",
                "gap_ref": "s0_to_l6_world_slot_bridge_missing",
            },
            "owner_writability": {
                "owner": "L6 intervention substrate resolver",
                "s0_registry_content_hash": _mapping(facts.get("s0_registry")).get(
                    "content_hash"
                ),
                "s0_education_entries": _mapping(facts.get("s0_registry")).get(
                    "education_relevant_entries"
                ),
                "l6_bundle_content_hash": _mapping(facts.get("l6_owner")).get(
                    "bundle_content_hash"
                ),
                "attempts": attempts,
                "positive_writable_count": len(writable),
                "status": "thin_or_zero_is_honest",
            },
            "substrate_registry": {
                "owner": _SUBSTRATE_REGISTRY_OWNER,
                "content_hash": _mapping(facts.get("s0_registry")).get(
                    "content_hash"
                ),
                "substrate_version_id": _mapping(facts.get("s0_registry")).get(
                    "substrate_version_id"
                ),
                "selected_entry_hashes": selected_registry_hashes,
                "registry_owner_query_ref": "owner_query_results.s0_registry",
                "selection_evidence": {
                    **_mapping(
                        _mapping(facts.get("s0_registry")).get("selection_evidence")
                    ),
                    "owner_query_ref": "owner_query_results.l2_selected_levers",
                    "owner_query_source_ref": l2_component.get(
                        "owner_query_source_ref"
                    ),
                    "query_id": l2_component.get("query_id"),
                    "query_content_hash": l2_component.get("query_content_hash"),
                    "query_response_content_hash": l2_component.get(
                        "response_content_hash"
                    ),
                },
                "authority_purpose": "candidate_evidence_intake_only",
            },
            "transport_context": {
                "owner": "L1 DCAT plus L2 exact concept presence",
                "covariates": covariate_entries,
                "source_context": facts["source_context"],
                "target_context": facts["target_context"],
                "status": "candidate_context_only_not_transport_authority",
            },
            "grounding_reference_coverage": {
                "owner": "L2 scholar knowledge graph",
                "coverage": {
                    key: l2_component[key]
                    for key in (
                        "variable_count",
                        "causal_claim_count",
                        "parameter_estimate_count",
                        "edge_count",
                        "transport_score_count",
                    )
                },
                "owner_query": {
                    "query_id": l2_component["query_id"],
                    "query_content_hash": l2_component["query_content_hash"],
                    "response_content_hash": l2_component["response_content_hash"],
                },
            },
        },
        "owner_query_results": {
            "s0_registry": {
                "owner": _SUBSTRATE_REGISTRY_OWNER,
                "content_hash": _mapping(facts.get("s0_registry")).get(
                    "content_hash"
                ),
                "substrate_version_id": _mapping(facts.get("s0_registry")).get(
                    "substrate_version_id"
                ),
                "registry_payload": _mapping(facts.get("s0_registry")).get(
                    "registry_payload"
                ),
            },
            "l1_selected_entry_details": l1_detail_query,
            "l2_selected_levers": {
                "query_id": l2_component["query_id"],
                "query_content_hash": l2_component["query_content_hash"],
                "response_content_hash": l2_component["response_content_hash"],
                "owner_query_source_ref": l2_component["owner_query_source_ref"],
                "rows": _list_of_mappings(facts.get("l2_levers")),
            },
            "l2_exact_domain_measure_names": facts["l2_exact_query"],
            "l1_selected_context_profiles": facts["l1_context_query"],
        },
    }
    payload["substrate_input_content_hash"] = (
        second_domain_substrate_input_content_hash(payload)
    )
    return payload


def _build_pack(
    root: Path,
    census: Mapping[str, Any],
    facts: Mapping[str, Any],
    smoke_problem: Mapping[str, Any],
    cycle_trace: Mapping[str, Any],
    gaps: Mapping[str, Any],
    substrate_input: Mapping[str, Any],
) -> dict[str, Any]:
    chosen = str(substrate_input["selected_domain"])
    expected_input_hash = second_domain_substrate_input_content_hash(substrate_input)
    if substrate_input.get("substrate_input_content_hash") != expected_input_hash:
        raise ValueError("cycle_substrate_input_projection_hash_mismatch")
    base_commit = N10A_BASE_COMMIT
    proof_head_commit = N10A_PROOF_HEAD_COMMIT
    changed_paths = _historical_task_changed_paths(
        root,
        base=base_commit,
        proof_head=proof_head_commit,
    )
    engine_paths = [path for path in changed_paths if path.startswith("src/polisyos/")]
    out_of_scope_paths = [path for path in changed_paths if not _task_scope_path_allowed(path)]
    n7_attempt = _mapping(facts.get("n7_attempt"))
    n7_runtime_metrics = _mapping(n7_attempt.get("runtime_metrics"))
    n7_content = {
        key: value for key, value in n7_attempt.items() if key != "runtime_metrics"
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "policy_design_case.gy_n10a.second_domain_pack",
        "rule_version": RULE_VERSION,
        "producer": PRODUCER,
        "selected_domain": chosen,
        "content_addressing": {
            "cache_semantics": "E1 content-addressed frozen manifest",
            "journal_semantics": "E6 gaps are explicit because existing N7 has no durable L2/L3 journal artifact",
            "live_attempt_semantics": "E8 one candidate lever per N6 grammar-fallback attempt",
        },
        "census_content_hash": census["census_content_hash"],
        "smoke_problem_content_hash": smoke_problem["smoke_problem_content_hash"],
        "cycle_trace_content_hash": cycle_trace["trace_content_hash"],
        "gap_report_content_hash": gaps["gap_report_content_hash"],
        "content_hash_excluded_fields": ["runtime_metrics"],
        "components": copy.deepcopy(substrate_input["components"]),
        "owner_query_results": copy.deepcopy(substrate_input["owner_query_results"]),
        "distinctness": {
            "first_vertical_comparator": _first_vertical_comparator(root),
            "selected_method_family": "non_panel_short_series",
            "computed_status": "must_pass_validator",
        },
        "n7_acquisition": {
            **n7_content,
            "gap_refs": [
                "owner_registration_derivation_missing",
                "journal_raw_evidence_persistence_missing",
                "s0_to_l6_world_slot_bridge_missing",
            ],
        },
        "runtime_metrics": {"n7_acquisition": n7_runtime_metrics},
        "zero_engine_code": {
            "scope_semantics": "historical_commit_range",
            "task_base_commit": base_commit,
            "proof_head_commit": proof_head_commit,
            "changed_paths": changed_paths,
            "changed_engine_paths": engine_paths,
            "out_of_scope_paths": out_of_scope_paths,
            "status": "pass" if not engine_paths and not out_of_scope_paths else "fail",
        },
        "capability_reality": {
            "state": "artifact_missing_and_bridge_missing_for_durable_lever_registration",
            "surface": "pack_manifest_and_gap_report",
            "surface_out_of_scope": False,
        },
    }
    content_addressing = _mapping(payload.get("content_addressing"))
    content_addressing["historical_source_pack_content_hash"] = (
        _historical_n10a_pack_content_hash(root)
    )
    content_addressing["substrate_input_content_hash"] = expected_input_hash
    payload["content_addressing"] = content_addressing
    return _with_content_hash(
        payload,
        "manifest_content_hash",
        excluded_fields=("runtime_metrics",),
    )


def _pack_l1_entry(row: Mapping[str, Any], role: str, query: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        "canonical_var": str(row["canonical_var"]),
        "role": role,
        "datasets": int(row["datasets"]),
        "dataset_ids": list(row["dataset_ids"]),
        "observations": int(row["observations"]),
        "geographic_units": int(row["geographic_units"]),
        "periods": int(row["periods"]),
        "min_period": row["min_period"],
        "max_period": row["max_period"],
        "owner_evidence": {
            "owner": "L1 DCAT ds_observations",
            "query_id": query["query_id"],
            "query_content_hash": query["query_content_hash"],
            "query_response_content_hash": query["response_content_hash"],
            "source_row_content_hash": row["row_content_hash"],
        },
    }
    return _with_content_hash(payload, "entry_content_hash")


def _pack_l2_lever_entry(
    row: Mapping[str, Any],
    query: Mapping[str, Any],
    *,
    selected_registry_entry_hash: str,
) -> dict[str, Any]:
    """Project one L2 causal owner row into its exact candidate lever entry."""

    payload = {
        "lever_id": _identifier(str(row["cause"])),
        "instrument": str(row["cause"]),
        "target_concept": str(row["effect"]),
        "status": "candidate_unbound",
        "selected_registry_entry_hash": selected_registry_entry_hash,
        "owner_evidence": {
            "owner": "L2 scholar knowledge graph ac_causal_claims",
            "query_id": query["query_id"],
            "query_content_hash": query["query_content_hash"],
            "query_response_content_hash": query["response_content_hash"],
            "source_row_content_hash": row["row_content_hash"],
            "claim_ids": row["claim_ids"],
        },
    }
    return _with_content_hash(payload, "entry_content_hash")


def _validate_artifact_hash(
    payload: Mapping[str, Any],
    field: str,
    issues: list[dict[str, Any]],
) -> None:
    if not payload:
        issues.append({"code": "artifact_payload_missing", "field": field})
        return
    declared_exclusions = frozenset(_list_of_strings(payload.get("content_hash_excluded_fields")))
    allowed_exclusions = _CONTENT_HASH_ALLOWED_EXCLUSIONS.get(field, frozenset())
    if declared_exclusions != allowed_exclusions:
        issues.append(
            {
                "code": "artifact_content_hash_exclusion_invalid",
                "field": field,
                "declared": sorted(declared_exclusions),
                "allowed": sorted(allowed_exclusions),
            }
        )
    expected = _hash(
        {
            key: value
            for key, value in payload.items()
            if key != field and key not in allowed_exclusions
        }
    )
    if payload.get(field) != expected:
        issues.append({"code": "artifact_content_hash_drift", "field": field})


def _validate_census_selection(census: Mapping[str, Any], issues: list[dict[str, Any]]) -> None:
    candidates = _mapping(census.get("candidates"))
    reconstructed = _rank_candidates({str(key): _mapping(value) for key, value in candidates.items()})
    decision = _mapping(census.get("decision"))
    if decision.get("ranking") != reconstructed:
        issues.append({"code": "census_ranking_not_recomputable"})
    eligible = [row for row in reconstructed if bool(row.get("eligible"))]
    expected_choice = str((eligible or reconstructed)[0].get("candidate_id", "")) if reconstructed else ""
    if decision.get("chosen_candidate") != expected_choice:
        issues.append({"code": "census_decision_not_measured_ranking"})
    if bool(decision.get("all_candidates_ineligible")) != (not bool(eligible)):
        issues.append({"code": "census_all_ineligible_status_drift"})
    timings = _mapping(_mapping(census.get("runtime_metrics")).get("query_timings_seconds"))
    if set(timings) != {
        "l1_candidate_aggregate",
        "l2_candidate_aggregate",
        "l2_candidate_exact_measure_names",
    } or any(
        not isinstance(value, (float, int)) or float(value) < 0.0 for value in timings.values()
    ):
        issues.append({"code": "census_query_timings_missing_or_invalid"})


def _validate_owner_derived_entries(
    census: Mapping[str, Any],
    pack: Mapping[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    chosen = str(pack.get("selected_domain") or "")
    candidate = _mapping(_mapping(census.get("candidates")).get(chosen))
    l1_census_rows = {
        str(row.get("canonical_var")): row
        for row in _list_of_mappings(_mapping(candidate.get("l1_dcat")).get("rows"))
    }
    components = _mapping(pack.get("components"))
    owner_queries = _mapping(pack.get("owner_query_results"))
    l1_details = _mapping(owner_queries.get("l1_selected_entry_details"))
    detail_rows = {
        str(row.get("canonical_var")): row
        for row in _list_of_mappings(l1_details.get("rows"))
    }
    for component_name, field, expected_role in (
        ("outcomes", "entries", "outcome"),
        ("transport_context", "covariates", "transport_covariate"),
    ):
        entries = _list_of_mappings(_mapping(components.get(component_name)).get(field))
        for entry in entries:
            evidence = entry.get("owner_evidence")
            canonical_var = str(entry.get("canonical_var") or "")
            detail = detail_rows.get(canonical_var)
            census_row = l1_census_rows.get(canonical_var)
            if not isinstance(evidence, Mapping) or detail is None or census_row is None:
                issues.append({"code": "pack_entry_not_owner_derived", "entry": canonical_var})
                continue
            if evidence.get("source_row_content_hash") != detail.get("row_content_hash"):
                issues.append({"code": "pack_entry_owner_evidence_drift", "entry": canonical_var})
            if int(entry.get("observations", -1)) != int(detail.get("observations", -2)):
                issues.append({"code": "pack_entry_l1_count_drift", "entry": canonical_var})
            if int(detail.get("observations", -1)) != int(census_row.get("observations", -2)):
                issues.append({"code": "pack_entry_census_count_drift", "entry": canonical_var})
            expected = _pack_l1_entry(detail, expected_role, l1_details)
            if entry != expected:
                issues.append(
                    {"code": "pack_entry_owner_projection_drift", "entry": canonical_var}
                )
    l2_query = _mapping(owner_queries.get("l2_selected_levers"))
    selected_registry_hashes = _list_of_strings(
        _mapping(components.get("substrate_registry")).get("selected_entry_hashes")
    )
    if len(selected_registry_hashes) != 1:
        issues.append({"code": "cycle_substrate_registry_selection_denominator_invalid"})
    lever_rows = {
        (str(row.get("cause")), str(row.get("effect"))): row
        for row in _list_of_mappings(l2_query.get("rows"))
    }
    for entry in _list_of_mappings(_mapping(components.get("lever_vocabulary")).get("entries")):
        evidence = entry.get("owner_evidence")
        key = (str(entry.get("instrument")), str(entry.get("target_concept")))
        source = lever_rows.get(key)
        if not isinstance(evidence, Mapping) or source is None:
            issues.append({"code": "pack_entry_not_owner_derived", "entry": key[0]})
            continue
        if evidence.get("source_row_content_hash") != source.get("row_content_hash"):
            issues.append({"code": "pack_entry_owner_evidence_drift", "entry": key[0]})
        if len(selected_registry_hashes) != 1:
            continue
        expected = _pack_l2_lever_entry(
            source,
            l2_query,
            selected_registry_entry_hash=selected_registry_hashes[0],
        )
        if entry != expected:
            issues.append({"code": "pack_entry_owner_projection_drift", "entry": key[0]})
    grounding = _mapping(components.get("grounding_reference_coverage"))
    expected_coverage = {
        key: _mapping(candidate.get("l2_scholar_kg")).get(key)
        for key in (
            "variable_count",
            "causal_claim_count",
            "parameter_estimate_count",
            "edge_count",
            "transport_score_count",
        )
    }
    if grounding.get("coverage") != expected_coverage:
        issues.append({"code": "grounding_coverage_owner_projection_drift"})
    expected_grounding_query = {
        "query_id": candidate.get("l2_scholar_kg", {}).get("query_id"),
        "query_content_hash": candidate.get("l2_scholar_kg", {}).get("query_content_hash"),
        "response_content_hash": candidate.get("l2_scholar_kg", {}).get("response_content_hash"),
    }
    if grounding.get("owner_query") != expected_grounding_query:
        issues.append({"code": "grounding_coverage_owner_evidence_drift"})
    transport = _mapping(components.get("transport_context"))
    profile_query = _mapping(owner_queries.get("l1_selected_context_profiles"))
    try:
        expected_source, expected_target = _select_context_pair(
            _list_of_mappings(profile_query.get("rows"))
        )
    except OwnerDataUnavailableError:
        issues.append({"code": "transport_context_owner_data_missing"})
    else:
        if transport.get("source_context") != expected_source or transport.get(
            "target_context"
        ) != expected_target:
            issues.append({"code": "transport_context_owner_projection_drift"})
    lever_entries = _list_of_mappings(_mapping(components.get("lever_vocabulary")).get("entries"))
    writability_attempts = _list_of_mappings(
        _mapping(components.get("owner_writability")).get("attempts")
    )
    if {str(item.get("instrument")) for item in lever_entries} != {
        str(item.get("instrument")) for item in writability_attempts
    }:
        issues.append({"code": "owner_writability_denominator_mismatch"})


def _validate_cycle_substrate_registry(
    root: Path,
    census: Mapping[str, Any],
    pack: Mapping[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    """Resolve and content-bind the registry evidence used by cycle intake."""

    addressing = _mapping(pack.get("content_addressing"))
    try:
        historical_hash = _historical_n10a_pack_content_hash(root)
    except RuntimeError as exc:
        issues.append(
            {"code": "historical_source_pack_unresolvable", "error": str(exc)}
        )
    else:
        if addressing.get("historical_source_pack_content_hash") != historical_hash:
            issues.append({"code": "historical_source_pack_content_hash_mismatch"})
    if addressing.get(
        "substrate_input_content_hash"
    ) != second_domain_substrate_input_content_hash(pack):
        issues.append({"code": "cycle_substrate_input_content_hash_mismatch"})

    components = _mapping(pack.get("components"))
    component = _mapping(components.get("substrate_registry"))
    owner_queries = _mapping(pack.get("owner_query_results"))
    owner_registry = _mapping(owner_queries.get("s0_registry"))
    registry_payload = _mapping(owner_registry.get("registry_payload"))
    if not component or not owner_registry or not registry_payload:
        issues.append({"code": "cycle_substrate_registry_payload_missing"})
        return
    try:
        registry = SubstrateRegistry.model_validate(registry_payload)
    except ValueError as exc:
        issues.append(
            {
                "code": "cycle_substrate_registry_payload_invalid",
                "error": str(exc),
            }
        )
        return
    if (
        component.get("owner") != _SUBSTRATE_REGISTRY_OWNER
        or owner_registry.get("owner") != _SUBSTRATE_REGISTRY_OWNER
        or registry.producer_ref != _SUBSTRATE_REGISTRY_PRODUCER
    ):
        issues.append({"code": "cycle_substrate_registry_producer_mismatch"})
    live_registry = _cached_owner_substrate_registry(root.resolve().as_posix())
    if registry.model_dump(mode="json") != live_registry.model_dump(mode="json"):
        issues.append({"code": "cycle_substrate_registry_owner_rederive_mismatch"})

    expected_version_id = (
        "substrate_version_" + registry.content_hash.removeprefix("sha256:")[:16]
    )
    if registry.substrate_version_id != expected_version_id:
        issues.append({"code": "cycle_substrate_registry_version_id_mismatch"})
    if (
        owner_registry.get("content_hash") != registry.content_hash
        or component.get("content_hash") != registry.content_hash
        or _mapping(components.get("owner_writability")).get(
            "s0_registry_content_hash"
        )
        != registry.content_hash
    ):
        issues.append({"code": "cycle_substrate_registry_content_hash_mismatch"})
    if (
        owner_registry.get("substrate_version_id") != registry.substrate_version_id
        or component.get("substrate_version_id") != registry.substrate_version_id
    ):
        issues.append({"code": "cycle_substrate_registry_version_projection_mismatch"})
    if component.get("registry_owner_query_ref") != "owner_query_results.s0_registry":
        issues.append({"code": "cycle_substrate_registry_owner_ref_mismatch"})
    if component.get("authority_purpose") != "candidate_evidence_intake_only":
        issues.append({"code": "cycle_substrate_registry_authority_boundary_missing"})

    selected_hashes = _list_of_strings(component.get("selected_entry_hashes"))
    if len(selected_hashes) != 1 or len(selected_hashes) != len(set(selected_hashes)):
        issues.append({"code": "cycle_substrate_registry_selection_denominator_invalid"})
        return
    entries_by_hash = {entry.entry_content_hash: entry for entry in registry.entries}
    selected_entry = entries_by_hash.get(selected_hashes[0])
    if selected_entry is None:
        issues.append({"code": "cycle_substrate_registry_selected_entry_unresolved"})
        return
    if selected_entry.layer.value != "L2":
        issues.append({"code": "cycle_substrate_registry_selected_entry_not_l2"})
    selection = _mapping(component.get("selection_evidence"))
    query = _mapping(owner_queries.get("l2_selected_levers"))
    chosen = str(pack.get("selected_domain") or "")
    try:
        historical_query = _historical_n10a_l2_query_evidence(
            root.resolve().as_posix()
        )
        canonical_source_ref = "repo://" + _repo_relative_mounted_evidence_path(
            root / DEFAULT_L2_SCHOLAR_KG_PATH,
            root,
        )
    except (RuntimeError, SourceHashCheckoutPathError) as exc:
        issues.append(
            {
                "code": "cycle_substrate_registry_historical_query_unresolvable",
                "error": str(exc),
            }
        )
        return
    try:
        current_query = _verified_l2_query_evidence(
            census,
            context="current",
        )
    except RuntimeError as exc:
        issues.append(
            {
                "code": "cycle_substrate_registry_query_census_mismatch",
                "error": str(exc),
            }
        )
        return
    if historical_query.owner_query_source_ref != canonical_source_ref:
        issues.append(
            {"code": "cycle_substrate_registry_historical_source_mismatch"}
        )
        return
    canonical_query = {
        "query_id": historical_query.query_id,
        "query_content_hash": historical_query.query_content_hash,
        "response_content_hash": historical_query.response_content_hash,
        "owner_query_source_ref": canonical_source_ref,
    }
    if (
        chosen != historical_query.candidate_id
        or current_query != historical_query
        or any(query.get(key) != value for key, value in canonical_query.items())
    ):
        issues.append({"code": "cycle_substrate_registry_query_census_mismatch"})

    live_query_entries = [
        entry
        for entry in live_registry.entries
        if entry.layer.value == "L2"
        and any(
            ref.split("#", 1)[0] == canonical_source_ref
            for ref in (*entry.provenance_refs, *entry.authority_refs)
        )
    ]
    if len(live_query_entries) != 1:
        issues.append(
            {
                "code": "cycle_substrate_registry_query_owner_denominator_invalid",
                "resolved_entry_count": len(live_query_entries),
            }
        )
    elif selected_hashes[0] != live_query_entries[0].entry_content_hash:
        issues.append(
            {"code": "cycle_substrate_registry_selected_entry_not_query_owner"}
        )
    expected_query_evidence = {
        "owner_query_ref": "owner_query_results.l2_selected_levers",
        "owner_query_source_ref": canonical_query["owner_query_source_ref"],
        "query_id": canonical_query["query_id"],
        "query_content_hash": canonical_query["query_content_hash"],
        "query_response_content_hash": canonical_query["response_content_hash"],
    }
    if any(selection.get(key) != value for key, value in expected_query_evidence.items()):
        issues.append({"code": "cycle_substrate_registry_selection_evidence_mismatch"})
    source_ref = str(selection.get("owner_query_source_ref") or "")
    source_matches = [
        ref
        for ref in (*selected_entry.provenance_refs, *selected_entry.authority_refs)
        if ref.split("#", 1)[0] == source_ref
    ]
    if not source_ref.startswith("repo://") or not source_matches:
        issues.append({"code": "cycle_substrate_registry_selection_evidence_mismatch"})

    lever_entries = _list_of_mappings(
        _mapping(components.get("lever_vocabulary")).get("entries")
    )
    if not lever_entries or {
        str(entry.get("selected_registry_entry_hash")) for entry in lever_entries
    } != set(selected_hashes):
        issues.append({"code": "cycle_substrate_lever_registry_binding_mismatch"})


def _validate_n7_attempt(
    root: Path,
    pack: Mapping[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    """Require one real, journal-first N7 attempt without granting it pack authority."""

    attempt = _mapping(pack.get("n7_acquisition"))
    if int(attempt.get("receipt_count", 0)) != 1 or not attempt.get("one_live_variable_per_attempt"):
        issues.append({"code": "n7_live_attempt_denominator_invalid"})
        return
    try:
        expected_input_hash = _n7_attempt_input_content_hash_from_pack(pack)
    except ValueError as exc:
        issues.append({"code": str(exc)})
    else:
        if attempt.get("attempt_input_content_hash") != expected_input_hash:
            issues.append({"code": "n7_attempt_input_content_hash_mismatch"})
    runtime_metrics = _mapping(pack.get("runtime_metrics"))
    operational = _mapping(runtime_metrics.get("n7_acquisition"))
    receipt_content = _mapping(attempt.get("receipt_content"))
    try:
        historical_pack = _historical_n10a_pack_payload(root)
    except RuntimeError as exc:
        issues.append({"code": "n7_historical_receipt_unresolvable", "error": str(exc)})
    else:
        historical_attempt = _mapping(historical_pack.get("n7_acquisition"))
        if (
            attempt.get("receipt_content_hash")
            != historical_attempt.get("receipt_content_hash")
            or receipt_content != _mapping(historical_attempt.get("receipt_content"))
            or attempt.get("raw_response_hash_checks")
            != historical_attempt.get("raw_response_hash_checks")
        ):
            issues.append({"code": "n7_historical_receipt_mismatch"})
    _validate_n7_receipt_evidence(attempt, operational, issues)


def _validate_n7_receipt_evidence(
    attempt: Mapping[str, Any],
    operational: Mapping[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    """Reconstruct and verify one journal-first N7 receipt without duplicate content."""

    receipt_content = _mapping(attempt.get("receipt_content"))
    time_paths = _n7_content_time_paths(receipt_content)
    if "receipt" in attempt or time_paths:
        issues.append({"code": "capture_time_content_bound", "paths": time_paths})
    if "receipt" in operational:
        issues.append({"code": "n7_operational_receipt_duplicate"})
    try:
        reconstructed_payload = _reconstruct_n7_receipt_payload(receipt_content, operational)
        receipt = AcquisitionReceipt.model_validate(reconstructed_payload)
    except ValueError as exc:
        code = (
            "n7_operational_capture_metadata_missing"
            if "n7_operational_capture_metadata_missing" in str(exc)
            else "n7_receipt_invalid"
        )
        issues.append({"code": code, "error": str(exc)})
        return
    expected_content = _n7_owner_evidence_projection(reconstructed_payload)
    if receipt_content != expected_content:
        issues.append({"code": "n7_receipt_content_projection_drift"})
    if attempt.get("receipt_content_hash") != _hash(expected_content):
        issues.append({"code": "n7_receipt_content_hash_drift"})
    expected_operational = _n7_operational_metadata(reconstructed_payload)
    if (
        operational.get("receipt_generated_at") != expected_operational.get("receipt_generated_at")
        or operational.get("planner_report_generated_at")
        != expected_operational.get("planner_report_generated_at")
        or operational.get("owner_capture_times") != expected_operational.get("owner_capture_times")
    ):
        issues.append({"code": "n7_operational_capture_metadata_drift"})
    receipt_issues = list(validate_acquisition_receipt(receipt))
    if receipt_issues:
        issues.append({"code": "n7_receipt_owner_validation_failed", "issues": receipt_issues})
    artifacts = _list_of_mappings(reconstructed_payload.get("owner_artifacts"))
    journals = _list_of_mappings(reconstructed_payload.get("journal_entries"))
    if receipt.compiled_spec_count != 1 or len(artifacts) != 1 or len(journals) != 1:
        issues.append({"code": "n7_live_attempt_denominator_invalid"})
    if any(item.get("status") != "journaled" for item in journals):
        issues.append({"code": "n7_journal_not_first"})
    raw_checks: list[dict[str, Any]] = []
    for artifact in artifacts:
        payload = _mapping(artifact.get("payload"))
        response = _mapping(payload.get("owner_response"))
        actual = payload.get("raw_owner_response_hash")
        expected = _n7_owner_response_hash(response)
        raw_checks.append(
            {
                "artifact_ref": artifact.get("artifact_ref"),
                "raw_response_hash": actual,
                "recomputed_raw_response_hash": expected,
                "matches": actual == expected,
            }
        )
        if artifact.get("owner_component") != "fabric.retrieval":
            issues.append({"code": "n7_owner_not_real_fabric_gateway"})
    if any(not row["matches"] for row in raw_checks):
        issues.append({"code": "n7_raw_response_hash_drift"})
    if attempt.get("raw_response_hash_checks") != raw_checks:
        issues.append({"code": "n7_recorded_raw_response_check_drift"})
    if attempt.get("owner_rederive_status") != "pass":
        issues.append({"code": "n7_owner_rederive_failed"})
    if attempt.get("pack_entry_rejection_reason") != _n7_pack_entry_rejection_reason(artifacts):
        issues.append({"code": "n7_registration_rejection_reason_drift"})
    if attempt.get("pack_entry_eligible") is not False or not attempt.get(
        "pack_entry_rejection_reason"
    ):
        issues.append({"code": "n7_registration_authority_boundary_leak"})


def _validate_distinctness(root: Path, pack: Mapping[str, Any], issues: list[dict[str, Any]]) -> None:
    comparator = _first_vertical_comparator(root)
    components = _mapping(pack.get("components"))
    outcomes = {
        str(entry.get("canonical_var"))
        for entry in _list_of_mappings(_mapping(components.get("outcomes")).get("entries"))
    }
    covariates = {
        str(entry.get("canonical_var"))
        for entry in _list_of_mappings(_mapping(components.get("transport_context")).get("covariates"))
    }
    levers = {
        str(entry.get("instrument"))
        for entry in _list_of_mappings(_mapping(components.get("lever_vocabulary")).get("entries"))
    }
    if outcomes.intersection(set(comparator["outcome_canonical_vars"])):
        issues.append({"code": "distinctness_outcome_overlap"})
    if covariates.intersection(set(comparator["transport_covariates"])):
        issues.append({"code": "distinctness_covariate_overlap"})
    if levers.intersection(set(comparator["lever_vocabulary"])):
        issues.append({"code": "distinctness_lever_overlap"})
    if pack.get("distinctness", {}).get("selected_method_family") == comparator["method_family"]:
        issues.append({"code": "distinctness_method_family_overlap"})
    if not covariates:
        issues.append({"code": "transport_covariate_denominator_empty"})


def _validate_coverage_denominators(
    census: Mapping[str, Any],
    pack: Mapping[str, Any],
    gaps: Mapping[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    candidates = _mapping(census.get("candidates"))
    for candidate_id, candidate_value in candidates.items():
        candidate = _mapping(candidate_value)
        configured = _list_of_strings(_mapping(candidate.get("selection_input")).get("l1_canonical_vars"))
        l1 = _mapping(candidate.get("l1_dcat"))
        observed = _list_of_mappings(l1.get("rows"))
        missing = _list_of_strings(l1.get("missing_canonical_vars"))
        if len(configured) != len(observed) + len(missing):
            issues.append({"code": "coverage_denominator_not_full", "candidate": candidate_id})
        l2 = _mapping(candidate.get("l2_scholar_kg"))
        feasibility = _mapping(candidate.get("lever_feasibility"))
        transport = _mapping(candidate.get("transport_feasibility"))
        ranking = next(
            (
                row
                for row in _list_of_mappings(_mapping(census.get("decision")).get("ranking"))
                if row.get("candidate_id") == candidate_id
            ),
            {},
        )
        ineligible_reasons = set(_list_of_strings(_mapping(ranking).get("ineligible_reasons")))
        top_levers = _list_of_mappings(l2.get("top_levers"))
        if int(l2.get("lever_cause_count", 0)) == 0 and (
            "owner_derived_lever_vocabulary_empty" not in ineligible_reasons
        ):
            issues.append({"code": "lever_coverage_gap_silently_omitted", "candidate": candidate_id})
        if len(_list_of_mappings(feasibility.get("l6_writability_attempts"))) != len(top_levers):
            issues.append({"code": "lever_writability_denominator_not_full", "candidate": candidate_id})
        if int(transport.get("jointly_measured_transport_count", 0)) == 0 and (
            "domain_transport_covariate_not_jointly_measured" not in ineligible_reasons
        ):
            issues.append({"code": "transport_coverage_gap_silently_omitted", "candidate": candidate_id})
    outcomes = _list_of_mappings(
        _mapping(_mapping(pack.get("components")).get("outcomes")).get("entries")
    )
    if not outcomes:
        issues.append({"code": "outcome_denominator_empty"})
    components = _mapping(pack.get("components"))
    lever_entries = _list_of_mappings(_mapping(components.get("lever_vocabulary")).get("entries"))
    if not lever_entries:
        issues.append({"code": "lever_coverage_denominator_empty"})
    writability_attempts = _list_of_mappings(
        _mapping(components.get("owner_writability")).get("attempts")
    )
    if not writability_attempts:
        issues.append({"code": "owner_writability_denominator_empty"})
    grounding_coverage = _mapping(
        _mapping(components.get("grounding_reference_coverage")).get("coverage")
    )
    if not grounding_coverage or any(
        not isinstance(value, int) or value < 0 for value in grounding_coverage.values()
    ):
        issues.append({"code": "grounding_coverage_denominator_invalid"})
    transport = _mapping(components.get("transport_context"))
    context_vars = {
        str(row.get("canonical_var"))
        for context_key in ("source_context", "target_context")
        for row in _list_of_mappings(_mapping(transport.get(context_key)).get("covariates"))
    }
    pack_covariates = {
        str(row.get("canonical_var"))
        for row in _list_of_mappings(transport.get("covariates"))
    }
    if not context_vars or not context_vars.issubset(pack_covariates):
        issues.append({"code": "transport_context_denominator_invalid"})
    if not _list_of_mappings(gaps.get("gaps")):
        issues.append({"code": "free_grow_gap_report_empty_without_proof"})


def _validate_gap_witnesses(
    root: Path,
    gaps: Mapping[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    """Re-resolve every recorded seam and reject absent or checkout-bound witnesses."""

    records = {
        str(gap.get("gap_id")): gap for gap in _list_of_mappings(gaps.get("gaps"))
    }
    expected_ids = set(GAP_WITNESS_SPECS)
    if set(records) != expected_ids:
        issues.append(
            {
                "code": "gap_witness_coverage_drift",
                "expected_gap_ids": sorted(expected_ids),
                "recorded_gap_ids": sorted(records),
            }
        )
    for gap_id, expected_spec in GAP_WITNESS_SPECS.items():
        record = records.get(gap_id)
        if record is None:
            continue
        owner_evidence = _mapping(record.get("owner_evidence"))
        witness = _mapping(owner_evidence.get("seam_witness"))
        source_path = witness.get("source_path")
        symbol = witness.get("symbol")
        if not isinstance(source_path, str) or not isinstance(symbol, str) or not symbol:
            issues.append({"code": "gap_witness_target_missing", "gap_id": gap_id})
            continue
        if Path(source_path).is_absolute():
            issues.append(
                {
                    "code": "source_hash_checkout_path_dependent",
                    "gap_id": gap_id,
                    "source_path": source_path,
                }
            )
            continue
        observed_spec = GapWitnessSpec(source_path=source_path, symbol=symbol)
        try:
            actual = _resolve_gap_witness(root, observed_spec)
        except SourceHashCheckoutPathError as exc:
            issues.append(
                {
                    "code": "source_hash_checkout_path_dependent",
                    "gap_id": gap_id,
                    "error": str(exc),
                }
            )
            continue
        except (FileNotFoundError, SyntaxError, GapWitnessTargetMissingError) as exc:
            issues.append(
                {
                    "code": "gap_witness_target_missing",
                    "gap_id": gap_id,
                    "error": str(exc),
                }
            )
            continue
        if observed_spec != expected_spec:
            issues.append(
                {
                    "code": "gap_witness_catalog_drift",
                    "gap_id": gap_id,
                    "expected_source_path": expected_spec.source_path,
                    "expected_symbol": expected_spec.symbol,
                    "recorded_source_path": source_path,
                    "recorded_symbol": symbol,
                }
            )
        if witness != actual:
            issues.append(
                {"code": "gap_witness_drift", "gap_id": gap_id}
            )


def _validate_smoke_terminal(
    smoke_problem: Mapping[str, Any],
    cycle_trace: Mapping[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    """Validate the real N6 trace and bind it to the frozen DesignProblem."""

    run_payload = _mapping(cycle_trace.get("generation_cycle_run"))
    try:
        run = GenerationCycleRun.model_validate(run_payload)
    except ValueError as exc:
        issues.append({"code": "smoke_generation_cycle_run_invalid", "error": str(exc)})
        return
    expected_problem_ref = _hash(_mapping(smoke_problem.get("design_problem")))
    if cycle_trace.get("smoke_problem_content_hash") != smoke_problem.get(
        "smoke_problem_content_hash"
    ) or run.design_problem_ref != expected_problem_ref:
        issues.append({"code": "smoke_design_problem_ref_drift"})
    if any(cycle.design_problem_ref != expected_problem_ref for cycle in run.cycles):
        issues.append({"code": "smoke_design_problem_ref_drift"})
    cycles = list(run.cycles)
    terminal_values = {item.value for item in SearchTerminalKind}
    if cycle_trace.get("execution_status") != "completed" or not cycles:
        issues.append({"code": "smoke_terminal_not_honest"})
        return
    if any(cycle.terminal_kind not in terminal_values for cycle in cycles):
        issues.append({"code": "smoke_terminal_not_honest"})
    text = _canonical_json(cycle_trace).lower()
    forbidden = ("first_vertical_mismatch", "generation_port_missing", "traceback")
    if any(token in text for token in forbidden):
        issues.append({"code": "smoke_terminal_not_honest"})
    actual_n6_issues = list(validate_generation_cycle_run(run))
    n6_issues = _list_of_mappings(cycle_trace.get("n6_validation_issues"))
    if _canonical_json(actual_n6_issues) != _canonical_json(n6_issues):
        issues.append({"code": "smoke_n6_validation_receipt_drift"})
    unexpected_n6_issues = [
        item
        for item in actual_n6_issues
        if str(item.get("code")) != "positive_cycle_denominator_missing"
    ]
    if unexpected_n6_issues:
        issues.append(
            {
                "code": "smoke_terminal_not_honest",
                "unexpected_n6_issues": unexpected_n6_issues,
            }
        )
    has_known_gap = any(
        str(item.get("code")) == "positive_cycle_denominator_missing" for item in actual_n6_issues
    )
    if has_known_gap and not bool(_mapping(cycle_trace.get("known_runtime_gap")).get("present")):
        issues.append({"code": "smoke_known_gap_not_disclosed"})


def _validate_zero_engine_code(root: Path, pack: Mapping[str, Any], issues: list[dict[str, Any]]) -> None:
    scope = _mapping(pack.get("zero_engine_code"))
    scope_semantics = scope.get("scope_semantics")
    base = scope.get("task_base_commit")
    proof_head = scope.get("proof_head_commit")
    recorded_paths = _list_of_strings(scope.get("changed_paths"))
    recorded = _list_of_strings(scope.get("changed_engine_paths"))
    recorded_out_of_scope = _list_of_strings(scope.get("out_of_scope_paths"))
    if proof_head != N10A_PROOF_HEAD_COMMIT:
        issues.append(
            {
                "code": "historical_receipt_rebased_to_moving_head",
                "recorded_proof_head": proof_head,
                "expected_proof_head": N10A_PROOF_HEAD_COMMIT,
            }
        )
    if base != N10A_BASE_COMMIT:
        issues.append(
            {
                "code": "historical_receipt_base_commit_drift",
                "recorded_base": base,
                "expected_base": N10A_BASE_COMMIT,
            }
        )
    literal_commits = all(
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
        for value in (base, proof_head)
    )
    if (
        scope_semantics != "historical_commit_range"
        or not literal_commits
        or base != N10A_BASE_COMMIT
        or proof_head != N10A_PROOF_HEAD_COMMIT
    ):
        issues.append(
            {
                "code": "diff_scope_unverifiable",
                "scope_semantics": scope_semantics,
                "task_base_commit": base,
                "proof_head_commit": proof_head,
            }
        )
    try:
        if (
            _git(root, "merge-base", N10A_BASE_COMMIT, N10A_PROOF_HEAD_COMMIT)
            != N10A_BASE_COMMIT
        ):
            issues.append({"code": "historical_receipt_base_not_ancestor"})
            return
        if (
            _git(root, "merge-base", N10A_PROOF_HEAD_COMMIT, "HEAD")
            != N10A_PROOF_HEAD_COMMIT
        ):
            issues.append({"code": "historical_receipt_proof_head_not_ancestor"})
            return
        actual_paths = _historical_task_changed_paths(
            root,
            base=N10A_BASE_COMMIT,
            proof_head=N10A_PROOF_HEAD_COMMIT,
        )
    except RuntimeError as exc:
        issues.append({"code": "diff_scope_unverifiable", "error": str(exc)})
        return
    actual = [path for path in actual_paths if path.startswith("src/polisyos/")]
    actual_out_of_scope = [
        path for path in actual_paths if not _task_scope_path_allowed(path)
    ]
    if recorded_paths != actual_paths:
        issues.append(
            {
                "code": "free_grow_changed_path_receipt_drift",
                "recorded_paths": recorded_paths,
                "actual_paths": actual_paths,
            }
        )
    if recorded_out_of_scope != actual_out_of_scope:
        issues.append(
            {
                "code": "free_grow_scope_receipt_drift",
                "recorded_paths": recorded_out_of_scope,
                "actual_paths": actual_out_of_scope,
            }
        )
    if recorded or actual:
        issues.append(
            {
                "code": "free_grow_violated_by_code_change",
                "recorded_paths": recorded,
                "actual_paths": actual,
            }
        )
    if recorded_out_of_scope or actual_out_of_scope:
        issues.append(
            {
                "code": "free_grow_violated_by_scope_change",
                "recorded_paths": recorded_out_of_scope,
                "actual_paths": actual_out_of_scope,
            }
        )


def _first_vertical_comparator(root: Path) -> dict[str, Any]:
    pinned_path = root / "architecture/policy_design_case/layer3_gx_pinned_request.json"
    value_path = root / "architecture/policy_design_case/layer3_gy_value_gate_contract.json"
    data_path = root / "architecture/policy_design_case/layer3_gy_data_state_substrate_contract.json"
    pinned = _read_json(pinned_path)
    value = _read_json(value_path)
    data = _read_json(data_path)
    g2 = _mapping(pinned.get("g2_request"))
    outcomes = {
        str(g2.get("effect", "")).rsplit(".", 1)[-1],
    }
    case_ids = _list_of_strings(
        _mapping(_mapping(data.get("behavioral_checks")).get("l1_l5_honesty")).get("case_ids")
    )
    for case_id in case_ids:
        if case_id.startswith("l1_") and case_id.endswith("_available"):
            outcomes.add(case_id.removeprefix("l1_").removesuffix("_available"))
    covariates = sorted(_recursive_values_for_key(value, "required_target_data"))
    levers = sorted(
        {
            str(g2.get("cause")),
            *(
                str(item.get("g2_variable_ref"))
                for item in _list_of_mappings(pinned.get("requested_constructs"))
                if item.get("role") == "cause"
            ),
        }
    )
    return {
        "case_id": pinned.get("case_id"),
        "source_hashes": {
            _repo_relative(pinned_path, root): _source_content_hash(root, pinned_path),
            _repo_relative(value_path, root): _source_content_hash(root, value_path),
            _repo_relative(data_path, root): _source_content_hash(root, data_path),
        },
        "outcome_canonical_vars": sorted(item for item in outcomes if item),
        "method_family": str(g2.get("data_modality")),
        "transport_covariates": covariates,
        "lever_vocabulary": [item for item in levers if item],
    }


def _run_query(
    path: Path,
    query_id: str,
    sql: str,
    parameters: Sequence[Any],
    query_timings: dict[str, float],
) -> dict[str, Any]:
    started = time.monotonic()
    con = duckdb.connect(str(path), read_only=True)
    try:
        cursor = con.execute(sql, list(parameters))
        columns = [str(item[0]) for item in cursor.description]
        rows = [_json_row(dict(zip(columns, row, strict=True))) for row in cursor.fetchall()]
    finally:
        con.close()
    query_timings[query_id] = round(max(0.0, time.monotonic() - started), 6)
    return {
        "query_id": query_id,
        "owner": "duckdb_read_only",
        "sql": sql,
        "parameters": _json_value(list(parameters)),
        "query_content_hash": _hash({"sql": sql, "parameters": _json_value(list(parameters))}),
        "rows": rows,
        "response_content_hash": _hash(rows),
    }


def _historical_task_changed_paths(
    root: Path,
    *,
    base: str,
    proof_head: str,
) -> list[str]:
    """Return only paths committed in the immutable historical proof range."""

    git_prefix = _git(root, "rev-parse", "--show-prefix")
    committed = _git(root, "diff", "--name-only", f"{base}..{proof_head}")
    paths = {
        _project_relative_git_path(path, git_prefix)
        for path in committed.splitlines()
        if path.strip()
    }
    return sorted(paths)


@lru_cache(maxsize=4)
def _historical_n10a_pack_json(repo_root: str) -> str:
    """Read the immutable N10a proof-head pack once per checkout."""

    root = Path(repo_root)
    git_prefix = _git(root, "rev-parse", "--show-prefix")
    historical_path = f"{git_prefix}{PACK_OUTPUT}" if git_prefix else PACK_OUTPUT
    return _git(
        root,
        "show",
        f"{N10A_PROOF_HEAD_COMMIT}:{historical_path}",
    )


def _historical_n10a_pack_payload(root: Path) -> dict[str, Any]:
    """Resolve and fully hash-verify the immutable N10a proof-head pack."""

    raw = _historical_n10a_pack_json(root.resolve().as_posix())
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("historical N10a pack is not valid JSON") from exc
    issues: list[dict[str, Any]] = []
    _validate_artifact_hash(payload, "manifest_content_hash", issues)
    if issues:
        raise RuntimeError(f"historical N10a pack hash invalid: {issues}")
    return payload


def _historical_n10a_pack_content_hash(root: Path) -> str:
    """Resolve and verify the immutable N10a proof-head pack identity."""

    payload = _historical_n10a_pack_payload(root)
    content_hash = str(payload.get("manifest_content_hash") or "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", content_hash):
        raise RuntimeError("historical N10a pack content hash missing")
    return content_hash


@lru_cache(maxsize=4)
def _historical_n10a_l2_query_evidence(
    repo_root: str,
) -> HistoricalL2QueryEvidence:
    """Resolve the selected L2 query from the immutable N10a census receipt."""

    root = Path(repo_root)
    git_prefix = _git(root, "rev-parse", "--show-prefix")
    historical_path = f"{git_prefix}{CENSUS_OUTPUT}" if git_prefix else CENSUS_OUTPUT
    raw = _git(
        root,
        "show",
        f"{N10A_PROOF_HEAD_COMMIT}:{historical_path}",
    )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("historical N10a census is not valid JSON") from exc
    issues: list[dict[str, Any]] = []
    _validate_artifact_hash(payload, "census_content_hash", issues)
    if issues:
        raise RuntimeError(f"historical N10a census hash invalid: {issues}")
    return _verified_l2_query_evidence(payload, context="historical N10a")


def _verified_l2_query_evidence(
    payload: Mapping[str, Any],
    *,
    context: str,
) -> HistoricalL2QueryEvidence:
    """Recompute one census L2 receipt and its selected-row projection."""

    candidate_id = str(_mapping(payload.get("decision")).get("chosen_candidate") or "")
    candidate_query = _mapping(
        _mapping(_mapping(payload.get("candidates")).get(candidate_id)).get(
            "l2_scholar_kg"
        )
    )
    query_id = str(candidate_query.get("query_id") or "")
    query_content_hash = str(candidate_query.get("query_content_hash") or "")
    response_content_hash = str(candidate_query.get("response_content_hash") or "")
    if (
        not candidate_id
        or not query_id
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", query_content_hash)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", response_content_hash)
    ):
        raise RuntimeError(f"{context} census L2 query evidence is incomplete")

    owner_query = _mapping(_mapping(payload.get("owner_queries")).get(query_id))
    owner_rows = _list_of_mappings(owner_query.get("rows"))
    matching_rows = [
        row for row in owner_rows if str(row.get("candidate_id") or "") == candidate_id
    ]
    candidate_row = {
        key: value
        for key, value in candidate_query.items()
        if key
        not in {
            "query_id",
            "query_content_hash",
            "response_content_hash",
            "owner_query_source_ref",
        }
    }
    recomputed_query_hash = _hash(
        {
            "sql": owner_query.get("sql"),
            "parameters": _json_value(owner_query.get("parameters")),
        }
    )
    recomputed_response_hash = _hash(owner_rows)
    if (
        owner_query.get("query_id") != query_id
        or owner_query.get("query_content_hash") != query_content_hash
        or owner_query.get("response_content_hash") != response_content_hash
        or recomputed_query_hash != query_content_hash
        or recomputed_response_hash != response_content_hash
        or len(matching_rows) != 1
        or matching_rows[0] != candidate_row
    ):
        raise RuntimeError(f"{context} owner query receipt is inconsistent")

    owner_path = str(
        _mapping(payload.get("owner_paths")).get("l2_scholar_kg") or ""
    )
    lexical_owner_path = Path(owner_path)
    if (
        not owner_path
        or lexical_owner_path.is_absolute()
        or ".." in lexical_owner_path.parts
    ):
        raise RuntimeError(f"{context} L2 owner path is not repo-relative")
    owner_query_source_ref = "repo://" + lexical_owner_path.as_posix()
    return HistoricalL2QueryEvidence(
        candidate_id=candidate_id,
        query_id=query_id,
        query_content_hash=query_content_hash,
        response_content_hash=response_content_hash,
        owner_query_source_ref=owner_query_source_ref,
    )


def _project_relative_git_path(path: str, git_prefix: str) -> str:
    """Strip the caller's Git subdirectory prefix from a path, when present."""

    return path.removeprefix(git_prefix) if git_prefix else path


def _task_scope_path_allowed(path: str) -> bool:
    """Return whether a changed path belongs to this data-only task surface."""

    return path in _TASK_SCOPE_ALLOWED_EXACT or path.startswith(_TASK_SCOPE_ALLOWED_PREFIXES)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def _resolve_gap_witness(root: Path, spec: GapWitnessSpec) -> dict[str, Any]:
    """Recompute one exact source seam without binding its checkout location."""

    source_path = _source_path_from_repo_relative(root, spec.source_path)
    if not source_path.is_file():
        raise GapWitnessTargetMissingError(
            f"gap witness source is absent: {spec.source_path}::{spec.symbol}"
        )
    source_text = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source_text)
    targets = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == spec.symbol
    ]
    if len(targets) != 1:
        raise GapWitnessTargetMissingError(
            f"gap witness target must resolve exactly once: {spec.source_path}::{spec.symbol}"
        )
    target = targets[0]
    segment = ast.get_source_segment(source_text, target)
    if not segment:
        raise GapWitnessTargetMissingError(
            f"gap witness target has no source segment: {spec.source_path}::{spec.symbol}"
        )
    canonical_path = _canonical_repo_relative_path(root, source_path)
    return {
        "source_path": canonical_path,
        "symbol": spec.symbol,
        "segment_content_hash": _hash(
            {
                "repo_relative_path": canonical_path,
                "symbol": spec.symbol,
                "source": segment,
            }
        ),
        "observed_call_names": sorted(
            {
                _call_name(node.func)
                for node in ast.walk(target)
                if isinstance(node, ast.Call)
            }
        ),
    }


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_call_name(node.value)}.{node.attr}"
    return "<dynamic>"


def _load_frozen_bundle(root: Path) -> dict[str, Any]:
    return {
        "census": _read_json(root / CENSUS_OUTPUT),
        "pack": _read_json(root / PACK_OUTPUT),
        "smoke_problem": _read_json(root / SMOKE_PROBLEM_OUTPUT),
        "cycle_trace": _read_json(root / CYCLE_TRACE_OUTPUT),
        "gaps": _read_json(root / GAP_REPORT_OUTPUT),
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_content_hash(repo_root: Path, source_path: Path) -> str:
    """Hash source text with its canonical repo-relative identity only."""

    canonical_path = _canonical_repo_relative_path(repo_root, source_path)
    return _hash(
        {
            "repo_relative_path": canonical_path,
            "source": source_path.resolve().read_text(encoding="utf-8"),
        }
    )


def _with_content_hash(
    payload: Mapping[str, Any],
    field: str,
    *,
    excluded_fields: Sequence[str] = (),
) -> dict[str, Any]:
    """Add a content hash, optionally excluding declared operational metadata."""

    normalized = {str(key): _json_value(value) for key, value in payload.items() if key != field}
    content_bound = {
        key: value for key, value in normalized.items() if key not in set(excluded_fields)
    }
    return {**normalized, field: _hash(content_bound)}


def _content_bound_canonical_json(payload: Mapping[str, Any]) -> str:
    """Serialize an artifact excluding only its explicitly allowed volatile metadata."""

    normalized = _mapping(payload)
    exclusion_values = frozenset(_list_of_strings(normalized.get("content_hash_excluded_fields")))
    allowed = frozenset().union(*_CONTENT_HASH_ALLOWED_EXCLUSIONS.values())
    return _canonical_json(
        {key: value for key, value in normalized.items() if key not in exclusion_values.intersection(allowed)}
    )


def _preserve_frozen_operational_metrics(bundle: dict[str, Any], root: Path) -> None:
    """Preserve nondeterministic operational metrics when content is unchanged."""

    artifacts = (
        ("census", CENSUS_OUTPUT, "census_content_hash"),
        ("cycle_trace", CYCLE_TRACE_OUTPUT, "trace_content_hash"),
    )
    for bundle_key, relative_path, hash_field in artifacts:
        path = root / relative_path
        if not path.is_file():
            continue
        frozen = _read_json(path)
        artifact = _mapping(bundle.get(bundle_key))
        if frozen.get(hash_field) != artifact.get(hash_field):
            continue
        frozen_metrics = _mapping(frozen.get("runtime_metrics"))
        if frozen_metrics:
            artifact["runtime_metrics"] = frozen_metrics
            bundle[bundle_key] = artifact


def _hash(value: Any) -> str:
    return gy_content_hash(_json_value(value))


def _canonical_json(value: Any) -> str:
    return json.dumps(_json_value(value), indent=2, sort_keys=True, ensure_ascii=True)


def _json_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_value(value) for key, value in row.items()}


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "item") and not isinstance(value, str):
        try:
            return _json_value(value.item())
        except (AttributeError, ValueError):
            pass
    return value


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list_of_mappings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [str(item) for item in value]


def _recursive_values_for_key(value: Any, key: str) -> set[str]:
    values: set[str] = set()
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            if child_key == key:
                values.update(_list_of_strings(child_value))
            values.update(_recursive_values_for_key(child_value, key))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            values.update(_recursive_values_for_key(item, key))
    return values


def _normalized_log(value: Any, maximum: float) -> float:
    if maximum <= 0:
        return 0.0
    return math.log1p(float(value or 0)) / maximum


def _normalized_linear(value: Any, maximum: float) -> float:
    if maximum <= 0:
        return 0.0
    return float(value or 0) / maximum


def _identifier(value: str) -> str:
    normalized = "".join(char if char.isalnum() else "_" for char in value.lower())
    normalized = "_".join(part for part in normalized.split("_") if part)
    return normalized if normalized and normalized[0].isalpha() else f"candidate_{normalized}"


def _repo_relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _repo_relative_mounted_evidence_path(path: Path, root: Path) -> str:
    """Return lexical repo identity for read-only mounts without resolving targets."""

    lexical_root = root.absolute()
    lexical_path = path.absolute()
    try:
        return lexical_path.relative_to(lexical_root).as_posix()
    except ValueError as exc:
        raise SourceHashCheckoutPathError(
            f"owner evidence path is outside repo root: {path}"
        ) from exc


def _canonical_repo_relative_path(repo_root: Path, source_path: Path) -> str:
    """Return a resolved source path relative to its checkout root, or fail closed."""

    root = repo_root.resolve()
    try:
        return source_path.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise SourceHashCheckoutPathError(
            f"source path is outside repo root: {source_path}"
        ) from exc


def _source_path_from_repo_relative(repo_root: Path, source_path: str) -> Path:
    """Resolve a recorded repo-relative source path while rejecting checkout paths."""

    raw_path = Path(source_path)
    if raw_path.is_absolute():
        raise SourceHashCheckoutPathError(
            f"source witness path must be repo-relative: {source_path}"
        )
    resolved = (repo_root.resolve() / raw_path).resolve()
    _canonical_repo_relative_path(repo_root, resolved)
    return resolved


def _render_report(report: Mapping[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(_canonical_json(report))
        return
    print(f"status={report.get('status')}")
    for issue in _list_of_mappings(report.get("issues")):
        print(f"- {issue.get('code')}: {issue}")
    print(f"wall_time_seconds={report.get('wall_time_seconds')}")


def main(argv: list[str] | None = None) -> int:
    """Run the frozen checker, writer, mutation, or live owner audit."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--rederive-audit", action="store_true")
    parser.add_argument("--corrupt-field-drift-check", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    selected = sum(
        bool(value)
        for value in (
            args.check,
            args.write,
            args.rederive_audit,
            args.corrupt_field_drift_check,
        )
    )
    if selected != 1:
        parser.error("select exactly one action")
    root = args.repo_root.resolve()
    try:
        if args.write:
            report = write(root)
        elif args.rederive_audit:
            report = rederive_audit(root)
        elif args.corrupt_field_drift_check:
            report = corrupt_field_drift_check(root)
        else:
            report = validate(root)
    except GapWitnessTargetMissingError as exc:
        report = {"status": "fail", "issues": [{"code": "gap_witness_target_missing", "error": str(exc)}]}
    except SourceHashCheckoutPathError as exc:
        report = {
            "status": "fail",
            "issues": [{"code": "source_hash_checkout_path_dependent", "error": str(exc)}],
        }
    except (OwnerDataUnavailableError, RuntimeError, ValueError) as exc:
        report = {"status": "fail", "issues": [{"code": "second_domain_pack_execution_failed", "error": str(exc)}]}
    _render_report(report, args.output_format)
    if args.corrupt_field_drift_check:
        return 1 if report.get("status") == "fail" else 2
    return 0 if report.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
