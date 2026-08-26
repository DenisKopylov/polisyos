#!/usr/bin/env python3
"""Validate the frozen Layer 3 GY-N8 value-gate contract."""

from __future__ import annotations

from time import perf_counter as _timing_perf_counter

_TIMING_STARTED_AT = _timing_perf_counter()

import argparse
import asyncio
import contextlib
import hashlib
import io
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any, get_args

from pydantic import ValidationError

from polisyos.core.contracts.value_outer_set import DataTrust, ValueOuterSet
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.design_problem import (
    AuthorityProfile,
    CandidateLever,
    CandidateLeverSpace,
    DesignObjective,
    DesignProblem,
    DesignStakeholder,
    EvidenceAcquisitionNeeds,
    JurisdictionTimeSemantics,
    NLProvenance,
    OutcomeOfInterest,
)
from polisyos.runtime.quality.generation_cycle import (
    ValueCalibrationReceipt,
    ValueEvaluationMode,
    ValueGateReceipt,
    ValueTransportReceipt,
)
from tools.lib.timing import run_timed_entrypoint

OUTPUT_PATH = "architecture/policy_design_case/layer3_gy_value_gate_contract.json"
SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy.value_gate_contract.v2"
VALUE_GATE_RULE_VERSION = "policyos.layer3.gy.n8.value_gate.v2"
CONTENT_HASH_EXCLUDED_TOP_LEVEL = {"contract_content_hash"}
LEGACY_POSITIVE_KEYS = frozenset({"frozen_positive_receipt", "frozen_value_receipts"})
NATIVE_CONTRACT_FAMILIES = (
    "posterior",
    "econometric",
    "forecasting",
    "distributional",
    "partial_identification",
    "transport",
)
FORK_B_CENSUS_CONTENT_HASH = (
    "sha256:2727227cc62c1e68fe5fbdaef486b0ebf96e9ee52c02dd5e735430ca500c0994"
)
FORK_B_CENSUS_RAW_HASH = "sha256:4b97e247d2e6e122a4f80287e39f230cf1f4e50990f8bec7ee9d4bf55c4d9740"
EXPECTED_MUTATION_IDS: tuple[str, ...] = (
    "value_input_read_from_runtime_hint",
    "empty_hints_production_owner_access",
    "audit_value_solve_fed_by_test_hints",
    "wmr_unavailable_not_acquire_gap",
    "value_outer_set_width_supplied_not_derived",
    "persisted_width_verification_removed",
    "proxy_forecast_narrow_set_rejected",
    "fixture_world_model_hash_rejected",
    "value_world_version_laundered",
    "dominance_timeout_forced_not_unknown",
    "simulate_only_shrank_k_world",
    "bad_forecast_minted_value",
    "pilot_mode_ran_without_eval_safety",
    "value_method_selection_fixed_default",
    "value_blocked_candidate_promoted_to_decision_front",
    "transport_tuple_reintroduced",
    "transport_measured_values_removed",
    "owner_treatment_assignment_required",
    "forged_relation_certificate_rejected",
    "value_projection_capability_contract_required",
    "catalog_replay_rejected",
    "truthfulness_auto_pass_rejected",
    "estimand_binding_required",
    "value_input_acquisition_route_required",
    "contract_projection_nonproduction",
)
EDITABLE_DIRECT_URL_SOURCE_FLIP_ID = "source_flip_editable_direct_url_address_rejected"
SOURCE_FLIP_MUTATION_IDS: tuple[str, ...] = (
    "source_flip_value_input_read_from_runtime_hint",
    "source_flip_empty_hints_production_owner_access",
    "source_flip_audit_value_solve_fed_by_test_hints",
    "source_flip_wmr_unavailable_not_acquire_gap",
    "source_flip_s10_owner_invocation_required",
    "source_flip_calibration_report_driven_refusal",
    "source_flip_width_tracks_real_did_ci",
    "source_flip_transport_real_solver_required",
    "source_flip_transport_tuple_reintroduced",
    "source_flip_transport_measured_values_removed",
    "source_flip_treatment_candidate_atom_binding_required",
    "source_flip_value_outer_set_width_supplied_not_derived",
    "source_flip_persisted_width_verification_removed",
    "source_flip_proxy_forecast_narrow_set_rejected",
    "source_flip_fixture_world_model_hash_rejected",
    "source_flip_value_world_version_laundered",
    "source_flip_dominance_timeout_forced_not_unknown",
    "source_flip_simulate_only_shrank_k_world",
    "source_flip_bad_forecast_minted_value",
    "source_flip_pilot_mode_ran_without_eval_safety",
    "source_flip_value_method_selection_fixed_default",
    "source_flip_value_blocked_candidate_promoted_to_decision_front",
    "source_flip_treatment_assignment_owner_required",
    "source_flip_forged_relation_certificate_rejected",
    "source_flip_value_projection_capability_contract_required",
    "source_flip_catalog_replay_rejected",
    EDITABLE_DIRECT_URL_SOURCE_FLIP_ID,
    "source_flip_truthfulness_auto_pass_rejected",
    "source_flip_estimand_binding_required",
    "source_flip_value_input_acquisition_route_required",
    "source_flip_contract_projection_nonproduction",
    "source_flip_world_identity_wmr_ref_binding_required",
    "source_flip_world_identity_problem_frame_binding_required",
    "source_flip_world_identity_target_slot_binding_required",
)


@dataclass(frozen=True, slots=True)
class ValueGateValidationResult:
    """Separate governed N8 failures from retained ambient diagnostics."""

    governing_issues: tuple[dict[str, Any], ...]
    ambient_findings: tuple[dict[str, Any], ...]


FROZEN_MUTATION_PROOFS: dict[str, str] = {
    "value_input_read_from_runtime_hint": (
        "Production N8 path has zero value-input runtime_hints reads."
    ),
    "empty_hints_production_owner_access": (
        "Empty runtime_hints reached real owner rows and refused missing owner assignment."
    ),
    "audit_value_solve_fed_by_test_hints": (
        "Audit live lane uses real owner access, advisor selection, and typed Fork-B refusal."
    ),
    "wmr_unavailable_not_acquire_gap": (
        "Missing cycle WMR fails as controller wiring, not acquire_data."
    ),
    "value_outer_set_width_supplied_not_derived": (
        "ValueOuterSet.model_validate rejects non-empty supplied width."
    ),
    "persisted_width_verification_removed": (
        "ValueOuterSet persisted intake rejects a width checksum that differs "
        "from deterministic lower/upper derivation."
    ),
    "proxy_forecast_narrow_set_rejected": "Proxy identification cannot emit a narrow/point set.",
    "fixture_world_model_hash_rejected": (
        "Placeholder WMR hash rejected; audit WMR is "
        "sha256:5e7e40f494e94986ddd5545faa256cb6ead5d564bc8abbc4c97ee4f23f535eb7."
    ),
    "value_world_version_laundered": ("Receipt refuses V1 value as authority for V2 world hash."),
    "dominance_timeout_forced_not_unknown": (
        "Timeout/approximation path returns unknown, not dominance."
    ),
    "simulate_only_shrank_k_world": "simulate_only receipt refuses K_world narrowing.",
    "bad_forecast_minted_value": (
        "uncalibrated:uncalibrated_forecast_minted_value; "
        "unsupported:unsupported_method_unavailable; "
        "regime_laundered:regime_laundered_forecast_minted_value; "
        "untransportable:untransportable_forecast_minted_value:4 validation errors for "
        "SelectionDiagram\n"
        "base_graph\n"
        "  Field required [type=missing, input_value={'invalid': 'selection-diagram'}, "
        "input_type=dict]\n"
        "    For further information visit https://errors.pydantic.dev/2.12/v/missing\n"
        "source_context\n"
        "  Field required [type=missing, input_value={'invalid': 'selection-diagram'}, "
        "input_type=dict]\n"
        "    For further information visit https://errors.pydantic.dev/2.12/v/missing\n"
        "target_context\n"
        "  Field required [type=missing, input_value={'invalid': 'selection-diagram'}, "
        "input_type=dict]\n"
        "    For further information visit https://errors.pydantic.dev/2.12/v/missing\n"
        "invalid\n"
        "  Extra inputs are not permitted [type=extra_forbidden, "
        "input_value='selection-diagram', input_type=str]\n"
        "    For further information visit https://errors.pydantic.dev/2.12/v/extra_forbidden"
    ),
    "pilot_mode_ran_without_eval_safety": (
        "EvalSafety blocks sandbox_pilot,field_pilot,deployment"
    ),
    "value_method_selection_fixed_default": (
        "Advisor selection uses the exact content-derived 55-method capability denominator."
    ),
    "value_blocked_candidate_promoted_to_decision_front": (
        "N6 promotion reducer refuses value_blocked summary."
    ),
    "transport_tuple_reintroduced": (
        "Education and first-vertical transport covariates derive from content-bound contexts."
    ),
    "transport_measured_values_removed": (
        "Unseen pack-shaped transport retains owner-measured source/target values."
    ),
    "owner_treatment_assignment_required": (
        "Caller/candidate treatment fields cannot open the observational value lane."
    ),
    "forged_relation_certificate_rejected": (
        "A shaped CG1 relation certificate cannot substitute for owner world knowledge."
    ),
    "value_projection_capability_contract_required": (
        "Token-matched methods without the two-sided native output contract are excluded."
    ),
    "catalog_replay_rejected": (
        "Method selection receipts bind the exact catalog and selector context."
    ),
    "truthfulness_auto_pass_rejected": (
        "Unverified native uncertainty returns a typed MethodValueRefusal."
    ),
    "estimand_binding_required": (
        "The same coefficient cannot launder a different treatment identity."
    ),
    "value_input_acquisition_route_required": (
        "Fork-B production refusal carries the canonical unsatisfied N7 any_of route."
    ),
    "contract_projection_nonproduction": (
        "All six native proofs are contract_only_nonproduction and cannot mint value authority."
    ),
}


@dataclass(frozen=True)
class _AuditAtom:
    intervention_id: str
    content_hash: str
    target_world_slots: tuple[str, ...] = ("firm_survival",)
    world_model_record_ref: str = "world_model_record_runtime_owner"


@dataclass(frozen=True)
class _AuditCandidate:
    candidate_id: str
    atom: _AuditAtom
    diversity_key: tuple[str, str, str, str]


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _ensure_src_path(repo_root: Path) -> None:
    src = repo_root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _hash(char: str) -> str:
    return "sha256:" + char * 64


@cache
def _audit_registry() -> Any:
    from polisyos.runtime.quality.substrate_registry import (
        build_substrate_registry_from_existing_catalogs,
    )

    return build_substrate_registry_from_existing_catalogs(_repo_root())


@cache
def _audit_world_record() -> Any:
    from polisyos.runtime.quality.generation_cycle import (
        _build_boundary_world_model_record,
    )

    registry = _audit_registry()
    return _build_boundary_world_model_record(
        repo_root=_repo_root(),
        problem=_audit_problem(),
        outcome="avg_income",
        policy_slot_ids=("avg_income",),
        substrate_registry=registry,
        selected_registry_entry_hashes=tuple(
            entry.entry_content_hash for entry in registry.entries
        ),
    )


@cache
def _canonical_first_vertical_lane() -> dict[str, Any]:
    """Resolve one real N4 shadow candidate and run it through the real N5 port."""

    from polisyos.runtime.quality.cycle_substrate import build_cycle_substrate_context
    from polisyos.runtime.quality.design_generation import (
        GenerationUnderAResult,
        ShadowGeneratedCandidate,
    )
    from polisyos.runtime.quality.generation_cycle import JointSimulationPort
    from polisyos.runtime.quality.intervention_substrate import (
        production_composed_world_model_record,
    )
    from polisyos.runtime.quality.substrate_registry import (
        build_substrate_registry_from_existing_catalogs,
    )
    from polisyos.runtime.quality.world_model_record import (
        resolve_intervention_atom_world_binding,
    )
    from tools.quality.validation import check_layer3_gy_design_generation_contract as n4

    validation = n4.validate(_repo_root())
    if validation.get("status") != "pass":
        raise RuntimeError("first_vertical_n4_artifact_invalid")
    artifact_path = _repo_root() / n4.OUTPUT_PATH
    artifact_bytes = artifact_path.read_bytes()
    artifact = json.loads(artifact_bytes)
    recordings = n4._load_recordings(_repo_root())
    selected: tuple[GenerationUnderAResult, ShadowGeneratedCandidate, Any, Any] | None = None
    for raw_result in artifact.get("generation_results") or ():
        result = GenerationUnderAResult.model_validate(raw_result)
        dispositions = {
            row.candidate_id: row
            for row in result.grounding_dispositions
            if row.disposition == "shadow_bound"
        }
        for candidate in result.candidates:
            disposition = dispositions.get(candidate.candidate_id)
            if (
                disposition is None
                or disposition.shadow_atom_content_hash != candidate.atom.content_hash
            ):
                continue
            matched = [
                (recording, n4._design_problem(recording))
                for recording in recordings
                if gy_content_hash(n4._design_problem(recording).model_dump(mode="json"))
                == candidate.atom.problem_frame_ref
            ]
            if len(matched) == 1 and result.design_problem_ref == (
                candidate.atom.problem_frame_ref
            ):
                recording, problem = matched[0]
                selected = (result, candidate, disposition, (recording, problem))
                break
        if selected is not None:
            break
    if selected is None:
        raise RuntimeError("first_vertical_shadow_candidate_unresolved")
    result, candidate, disposition, recording_problem = selected
    recording, problem = recording_problem
    world = production_composed_world_model_record(_repo_root())
    binding = resolve_intervention_atom_world_binding(candidate.atom, world)
    registry = build_substrate_registry_from_existing_catalogs(_repo_root())
    if registry.content_hash != world.substrate_registry_ref.content_hash:
        raise RuntimeError("first_vertical_registry_wmr_mismatch")
    selected_hashes = tuple(
        entry.entry_content_hash for entry in world.substrate_registry_ref.resolved_entries
    )
    substrate_input_hash = gy_content_hash(
        {
            "design_problem_ref": candidate.atom.problem_frame_ref,
            "substrate_registry_content_hash": registry.content_hash,
            "world_model_record_content_hash": world.content_hash,
            "selected_registry_entry_hashes": selected_hashes,
        }
    )
    context = build_cycle_substrate_context(
        design_problem_ref=candidate.atom.problem_frame_ref,
        domain=problem.domain,
        substrate_registry=registry,
        selected_registry_entry_hashes=selected_hashes,
        world_model_record=world,
        intervention_substrate=None,
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=None,
        substrate_input_content_hash=substrate_input_hash,
    )
    simulation = JointSimulationPort(
        repo_root=_repo_root(),
        cycle_substrate_context=context,
    )(
        candidate=candidate,
        problem=problem,
        cycle_index=0,
    )
    candidate_payload = candidate.model_dump(mode="json")
    return {
        "problem": problem,
        "candidate": candidate,
        "disposition": disposition,
        "simulation": simulation,
        "cycle_substrate_context": context,
        "world_model_record": world,
        "world_binding": binding,
        "generation_result_ref": result.design_problem_ref,
        "generation_result": result,
        "recording_id": str(recording.get("recording_id") or ""),
        "n4_artifact_ref": n4.OUTPUT_PATH,
        "n4_artifact_sha256": "sha256:" + hashlib.sha256(artifact_bytes).hexdigest(),
        "candidate_content_hash": gy_content_hash(candidate_payload),
    }


def _quiet_call(func: Callable[[], Any]) -> Any:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        return func()


@cache
def _run_real_first_vertical_cycle() -> Any:
    """Replay the real N4 result through N6/N5/N8 and the canonical N7 router."""

    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        PendingN9PromotionPort,
    )
    from polisyos.scientist.orchestration.engine.budget import (
        BudgetLimit,
        BudgetState,
    )

    lane = _canonical_first_vertical_lane()
    expected_problem_ref = gy_content_hash(lane["problem"].model_dump(mode="json"))

    class _ContentBoundN4ReplayPort:
        async def __call__(
            self,
            problem: DesignProblem,
            *,
            cycle_index: int,
        ) -> Any:
            if cycle_index != 0:
                raise RuntimeError("n8_first_vertical_replay_cycle_drift")
            if gy_content_hash(problem.model_dump(mode="json")) != expected_problem_ref:
                raise RuntimeError("n8_first_vertical_replay_problem_drift")
            return lane["generation_result"]

    controller = GenerationCycleController(
        generation_port=_ContentBoundN4ReplayPort(),
        promotion_port=PendingN9PromotionPort(),
        repo_root=_repo_root(),
        cycle_substrate_context=lane["cycle_substrate_context"],
        authority_scope="contract_testing",
    )
    return _quiet_call(
        lambda: asyncio.run(
            controller.run(
                lane["problem"],
                budget_state=BudgetState(
                    limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
                ),
                min_cycles=1,
                max_cycles=1,
            )
        )
    )


def build_payload(
    repo_root: Path | None = None,
    *,
    expected_source_freeze: str,
) -> dict[str, Any]:
    """Build the byte-stable N8 v2 Fork-B contract from canonical owners."""

    repo_root = (repo_root or _repo_root()).resolve()
    _ensure_src_path(repo_root)
    denominators = _quiet_call(
        lambda: _catalog_denominators(
            expected_source_freeze,
            repo_root,
        )
    )
    dependency_authority = denominators["catalog_dependency_authority"]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "rule_version": VALUE_GATE_RULE_VERSION,
        "gy_lifecycle_marker": SCHEMA_VERSION,
        "produced_by": "tools/quality/validation/check_layer3_gy_value_gate_contract.py",
        "status": "not_established",
        "catalog_dependency_authority": dependency_authority,
        "retained_capability_label": "producer_missing",
    }
    payload["contract_content_hash"] = _content_hash(payload)
    return payload


def _build_historical_candidate_payload(repo_root: Path) -> dict[str, Any]:
    """Build the private pre-authority projection for legacy mutation witnesses."""

    repo_root = repo_root.resolve()
    _ensure_src_path(repo_root)
    denominators = _candidate_catalog_denominators()
    production_run = _quiet_call(_run_real_first_vertical_cycle)
    education_observation = _quiet_call(_run_real_education_value_refusal)
    production_refusal = _normalized_first_vertical_data_gap_receipt(production_run)
    education_refusal = _normalized_refusal_receipt(
        education_observation,
        receipt_kind="education_estimand_binding_refusal",
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "rule_version": VALUE_GATE_RULE_VERSION,
        "gy_lifecycle_marker": SCHEMA_VERSION,
        "produced_by": "tools/quality/validation/check_layer3_gy_value_gate_contract.py",
        "disposition": {
            "task": "GY-N8",
            "disposition": "landed_with_typed_fork_b_residual",
            "owner_surface": "polisyos.runtime.quality.generation_cycle.FoundryValuePort",
            "selector_surface": "polisyos.foundry.methods.selection.select_value_method_for_problem",
            "parallel_value_engine": "blocked_by_P27",
        },
        "pattern_pass": {
            "relevant_ids": [
                "P05",
                "P10",
                "P14",
                "P27",
                "P29",
                "P30",
                "P31",
                "P32",
                "P37",
            ],
            "target_correct_pattern": (
                "owner-resolved world knowledge gates production value; the method "
                "denominator is builtins-only with canonical discovery and runtime "
                "provenance, while ambient inputs are separately bound and quarantined"
            ),
            "capability_labels": [
                "producer_missing:owner_rollout_assignment",
                "bridge_missing:certified_skg_identity_bridge",
            ],
            "acceptance_signal": (
                "real advisor selections end in typed honest refusals; six native "
                "families project contract-only uncertainty; catalog provenance drift "
                "fails with a named dimension; no value_ready is fabricated"
            ),
        },
        "denominators": denominators,
        "fork_b_census_receipt": _fork_b_census_receipt(repo_root),
        "production_refusal": production_refusal,
        "acquisition_routing": _acquisition_routing_receipt(production_run),
        "education_refusal": education_refusal,
        "native_projector_contract_proofs": _native_projector_contract_proofs(),
        "projector_refusal_proofs": _projector_refusal_proofs(),
        "transport_component_proofs": _transport_component_proofs(),
        "mode_gates": {
            "simulate_only": "cannot_narrow_k_world",
            "retrospective": "requires_data_trust",
            "measurement_audit": "requires_data_trust",
            "sandbox_pilot": "blocked_pending_GY_O0_eval_safety",
            "field_pilot": "blocked_pending_GY_O0_eval_safety",
            "deployment": "blocked_pending_GY_O0_eval_safety",
        },
        "honest_residuals": {
            "production_value": "owner_outcome_data_unavailable_routed_to_N7",
            "education_value": "method_estimand_binding_mismatch",
            "non_panel_positive": (
                "substrate_gated: no owner-backed positive in either domain; "
                "contract projector proven over six native families"
            ),
            "latent_assignment_or_identity_bridge": (
                "not_current_blocker; acquire any_of(owner_rollout_assignment,"
                "certified_skg_identity_bridge) after outcome rows exist"
            ),
            "promotion": "not_reached_and_not_expected",
            "authority_posture": "writability_zero_and_CG2_production_freeze",
        },
        "decisive_mutation_expectations": _mutation_expectations(),
        "source_flip_mutation_harness": {
            "mode": "--source-flip-mutations",
            "routine_check_runs_mutations": False,
            "mutation_ids": list(SOURCE_FLIP_MUTATION_IDS),
            "property": (
                "remove one runtime property, require semantic RED, and restore exact bytes"
            ),
        },
        "compute_economics": {
            "routine_check_live_owner_reads": True,
            "live_resolve_flag": "--rederive-audit",
            "cache_rule": "catalog_context_WMR_and_owner_rows_reused_by_content_hash",
            "wall_time_recorded_by_validator": True,
            "wall_time_reported_outside_byte_stable_artifact": True,
            "timestamps_in_content_hash": False,
        },
    }
    payload["contract_content_hash"] = _content_hash(payload)
    return payload


@cache
def _candidate_catalog_denominator_evidence_cached() -> tuple[dict[str, Any], dict[str, object]]:
    from polisyos.foundry.extensions.discovery import (
        discover_foundry_method_components,
    )
    from polisyos.foundry.extensions.registry import (
        controlled_builtin_foundry_method_registry_scope,
    )
    from polisyos.foundry.methods.catalog.snapshot import (
        _build_candidate_method_catalog_provenance_manifest,
        build_method_catalog_snapshot,
    )
    from polisyos.foundry.methods.selection import reachable_value_method_fqns

    with controlled_builtin_foundry_method_registry_scope() as (
        registry,
        registry_report,
    ):
        registered = registry_report.registry_fqns
        first = build_method_catalog_snapshot(
            registry=registry,
            run_id="GY-N10-stage2-n8-v2",
            registry_report=registry_report,
            require_bound_discovery=True,
        )
        second = build_method_catalog_snapshot(
            registry=registry,
            run_id="GY-N10-stage2-n8-v2",
            registry_report=registry_report,
            require_bound_discovery=True,
        )
        value_methods = reachable_value_method_fqns(
            registry=registry,
            catalog_snapshot=first,
        )
    ambient_report = discover_foundry_method_components(
        include_builtins=False,
        include_entry_points=True,
        include_dev_scan=True,
    )
    if ambient_report.manifest is None:
        raise RuntimeError("value_catalog_ambient_discovery_manifest_missing")
    catalog_fqns = tuple(entry.fqn for entry in first.entries)
    if catalog_fqns != registered or tuple(entry.fqn for entry in second.entries) != registered:
        raise RuntimeError("value_catalog_registry_denominator_mismatch")
    if first.snapshot_id != second.snapshot_id:
        raise RuntimeError("value_catalog_snapshot_nondeterministic")
    encoded = json.dumps(
        value_methods,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    denominator_values = {
        "evaluation_modes": list(get_args(ValueEvaluationMode)),
        "identification_statuses": ["point", "partial", "proxy"],
        "registered_method_count": len(registered),
        "catalog_entry_count": len(catalog_fqns),
        "catalog_matches_registry": True,
        "catalog_snapshot_id": first.snapshot_id,
        "catalog_snapshot_stable": True,
        "value_capable_method_count": len(value_methods),
        "value_capable_methods": list(value_methods),
        "value_capable_fqn_set_hash": "sha256:" + hashlib.sha256(encoded).hexdigest(),
        "native_contract_families": list(NATIVE_CONTRACT_FAMILIES),
    }
    additional_predicates = [
        {
            "predicate": predicate,
            "classification": "recomputed",
            "decisive": True,
            "fail_closed_action": "reject",
        }
        for predicate in (
            "catalog_registry_denominator_equality",
            "catalog_snapshot_content_identity",
            "catalog_snapshot_repeatability",
            "value_capability_owner_reconciliation",
            "value_capability_set_hash_derivation",
            "evaluation_mode_taxonomy_derivation",
            "identification_status_taxonomy_derivation",
            "native_contract_family_taxonomy_derivation",
        )
    ]
    governed_basis = [
        "governed_discovery_policy",
        "governed_registry_content_binding",
        "ambient_discovery_exclusion_policy",
        "registry_matches_governed_manifest",
    ]
    predicate_bindings = {
        "evaluation_modes": ["evaluation_mode_taxonomy_derivation"],
        "identification_statuses": ["identification_status_taxonomy_derivation"],
        "registered_method_count": [
            *governed_basis,
            "catalog_registry_denominator_equality",
        ],
        "catalog_entry_count": [
            *governed_basis,
            "catalog_registry_denominator_equality",
        ],
        "catalog_matches_registry": [
            *governed_basis,
            "catalog_registry_denominator_equality",
        ],
        "catalog_snapshot_id": [
            *governed_basis,
            "catalog_snapshot_content_identity",
        ],
        "catalog_snapshot_stable": [
            *governed_basis,
            "catalog_snapshot_repeatability",
        ],
        "value_capable_method_count": [
            *governed_basis,
            "value_capability_owner_reconciliation",
        ],
        "value_capable_methods": [
            *governed_basis,
            "value_capability_owner_reconciliation",
        ],
        "value_capable_fqn_set_hash": [
            "value_capability_owner_reconciliation",
            "value_capability_set_hash_derivation",
        ],
        "native_contract_families": ["native_contract_family_taxonomy_derivation"],
    }
    catalog_provenance = _build_candidate_method_catalog_provenance_manifest(
        first,
        registry_report=registry_report,
        ambient_manifest=ambient_report.manifest,
        additional_predicate_provenance=additional_predicates,
        predicate_bindings=predicate_bindings,
    )
    return (
        {**denominator_values, "catalog_provenance": catalog_provenance},
        ambient_report.manifest.content_payload(),
    )


@cache
def _candidate_catalog_denominators_cached() -> dict[str, Any]:
    return _candidate_catalog_denominator_evidence_cached()[0]


def _candidate_catalog_denominators() -> dict[str, Any]:
    return json.loads(json.dumps(_candidate_catalog_denominators_cached(), sort_keys=True))


@cache
def _catalog_denominator_evidence_cached(
    expected_source_freeze: str,
    repo_root: Path,
) -> tuple[dict[str, Any], dict[str, object]]:
    """Resolve the Foundry owner and stop at its exact typed non-receipt."""

    from polisyos.foundry.methods.catalog.dependency_authority import (
        AbsoluteRequestPath,
        MethodCatalogDependencyAuthorityRequest,
    )
    from polisyos.foundry.methods.catalog.snapshot import (
        build_method_catalog_provenance_manifest,
        build_method_catalog_runtime_identity,
    )

    resolved_root = repo_root.resolve()
    request = MethodCatalogDependencyAuthorityRequest(
        authority_purpose="n8_method_catalog_reconstruction",
        expected_source_freeze_commit=expected_source_freeze,
        production_data_root=AbsoluteRequestPath(value=resolved_root / "production_data"),
        environment_root=AbsoluteRequestPath(value=resolved_root / ".venv"),
    )
    sentinel = object()
    runtime_result = build_method_catalog_runtime_identity(
        sentinel,  # type: ignore[arg-type]
        dependency_authority_request=request,
    )
    provenance_result = build_method_catalog_provenance_manifest(
        sentinel,  # type: ignore[arg-type]
        registry_report=sentinel,  # type: ignore[arg-type]
        ambient_manifest=sentinel,  # type: ignore[arg-type]
        dependency_authority_request=request,
    )
    if runtime_result != provenance_result:
        raise RuntimeError("catalog_dependency_authority_builder_disagreement")
    return (
        {
            "catalog_dependency_authority": runtime_result.model_dump(mode="json"),
        },
        {},
    )


def _catalog_denominators(
    expected_source_freeze: str,
    repo_root: Path,
) -> dict[str, Any]:
    return json.loads(
        json.dumps(
            _catalog_denominator_evidence_cached(
                expected_source_freeze,
                repo_root,
            )[0],
            sort_keys=True,
        )
    )


def _reachable_value_methods() -> tuple[str, ...]:
    return tuple(_candidate_catalog_denominators_cached()["value_capable_methods"])


def _fork_b_census_receipt(repo_root: Path) -> dict[str, Any]:
    from tools.quality.validation import check_layer3_gy_n10_cg1_l2_relation_census

    path = repo_root / ("architecture/policy_design_case/layer3_gy_n10_cg1_l2_relation_census.json")
    census = _load_json(path)
    summary = check_layer3_gy_n10_cg1_l2_relation_census._validate(census)
    receipt = {
        "artifact_ref": str(path.relative_to(repo_root)),
        "fork": "B",
        "authority": "shadow_read_only_no_bind",
        "content_hash": census.get("content_hash"),
        "raw_full_table_content_hash": census.get("raw_full_table_content_hash"),
        "numeric_identities": summary.get("numeric_identities"),
        "numeric_edge_bindings": summary.get("numeric_edge_bindings"),
        "relation_rows": summary.get("relation_rows"),
        "relation_counts": summary.get("relation_counts"),
        "usable_certified_relations": 0,
        "acquisition_disposition": (
            "any_of(owner_rollout_assignment,certified_skg_identity_bridge)"
        ),
    }
    if receipt["content_hash"] != FORK_B_CENSUS_CONTENT_HASH:
        raise RuntimeError("fork_b_census_content_hash_drift")
    if receipt["raw_full_table_content_hash"] != FORK_B_CENSUS_RAW_HASH:
        raise RuntimeError("fork_b_census_raw_hash_drift")
    return receipt


def _normalized_refusal_receipt(
    observation: Any,
    *,
    receipt_kind: str,
) -> dict[str, Any]:
    selection = observation.method_selection_receipt
    if selection is None:
        raise RuntimeError(f"{receipt_kind}:method_selection_receipt_missing")
    payload = {
        "schema_version": "policyos.layer3.gy.n8.value_refusal_receipt.v2",
        "receipt_kind": receipt_kind,
        "candidate_id": observation.candidate_id,
        "status": observation.status,
        "decision_grade": observation.decision_grade,
        "authority_blockers": list(observation.authority_blockers),
        "reason": observation.reason,
        "evaluation_mode": observation.evaluation_mode,
        "selected_method_fqn": observation.selected_method_fqn,
        "method_selection_receipt": selection.model_dump(mode="json"),
        "value_data_profile_content_hash": observation.value_data_profile_content_hash,
        "world_model_record_content_hash": observation.world_model_record_content_hash,
        "value_receipt": None,
        "acquisition_requirement": (
            observation.acquisition_requirement.requirement_gap_id
            if observation.acquisition_requirement is not None
            else None
        ),
    }
    return {**payload, "content_hash": gy_content_hash(payload)}


def _normalized_first_vertical_data_gap_receipt(run: Any) -> dict[str, Any]:
    """Freeze the real N4→N8 owner-data refusal without inventing selection."""

    lane = _canonical_first_vertical_lane()
    if len(run.cycles) != 1:
        raise RuntimeError("first_vertical_cycle_denominator_drift")
    cycle = run.cycles[0]
    observation = cycle.value_port
    gap = observation.acquisition_requirement
    if gap is None:
        raise RuntimeError("first_vertical_l1_acquisition_requirement_missing")
    availability = dict(gap.metadata.get("availability") or {})
    if availability.get("source") is not None:
        raise RuntimeError("first_vertical_availability_shape_drift")
    payload = {
        "schema_version": "policyos.layer3.gy.n8.value_refusal_receipt.v2",
        "receipt_kind": "first_vertical_owner_data_gap",
        "candidate_id": observation.candidate_id,
        "candidate_content_hash": cycle.selected_candidate_content_hash,
        "candidate_atom_content_hash": lane["candidate"].atom.content_hash,
        "design_problem_ref": cycle.design_problem_ref,
        "n4_artifact_ref": lane["n4_artifact_ref"],
        "n4_artifact_sha256": lane["n4_artifact_sha256"],
        "n4_recording_id": lane["recording_id"],
        "status": observation.status,
        "decision_grade": observation.decision_grade,
        "authority_blockers": list(observation.authority_blockers),
        "reason": observation.reason,
        "evaluation_mode": observation.evaluation_mode,
        "selection_stage": "not_reached_owner_data_unavailable",
        "selected_method_fqn": None,
        "method_selection_receipt": None,
        "value_data_profile_content_hash": None,
        "world_model_record_id": lane["world_model_record"].world_model_record_id,
        "world_model_record_content_hash": observation.world_model_record_content_hash,
        "world_binding": lane["world_binding"].model_dump(mode="json"),
        "simulation_status": cycle.simulation.status,
        "k_world_ref_before": cycle.simulation.k_world_ref_before,
        "k_world_ref_after": cycle.simulation.k_world_ref_after,
        "owner_availability": availability,
        "value_receipt": None,
        "acquisition_requirement": gap.requirement_gap_id,
    }
    return {**payload, "content_hash": gy_content_hash(payload)}


def _acquisition_routing_receipt(run: Any) -> dict[str, Any]:
    if len(run.cycles) != 1:
        raise RuntimeError("fork_b_acquisition_cycle_denominator_drift")
    cycle = run.cycles[0]
    gap = cycle.value_port.acquisition_requirement
    if gap is None:
        raise RuntimeError("fork_b_acquisition_requirement_missing")
    report = cycle.acquisition_routing_report
    if report is None or len(report.acquisition_records) != 1:
        raise RuntimeError("fork_b_acquisition_planner_report_missing")
    report_payload = report.model_dump(mode="json")
    report_payload.pop("generated_at", None)
    payload = {
        "schema_version": "policyos.layer3.gy.n8.acquisition_routing_receipt.v2",
        "terminal_kind": cycle.terminal_kind,
        "selected_candidate_ref": cycle.selected_candidate_ref,
        "selected_candidate_content_hash": cycle.selected_candidate_content_hash,
        "requirement_gap": gap.model_dump(mode="json"),
        "planner_report": report_payload,
        "acquisition_receipt": None,
        "simulated_reentry": False,
    }
    return {**payload, "content_hash": gy_content_hash(payload)}


@cache
def _education_lane() -> tuple[DesignProblem, Any, Any]:
    from tools.quality.validation import check_layer3_gy_second_domain_pack

    bundle = check_layer3_gy_second_domain_pack._load_frozen_bundle(_repo_root())
    problem = DesignProblem.model_validate(bundle["smoke_problem"]["design_problem"])
    context = check_layer3_gy_second_domain_pack._build_frozen_cycle_substrate_context(
        _repo_root(),
        bundle=bundle,
        design_problem=problem,
    )
    grounding = bundle["cycle_trace"]["stage_attempts"]["grounding"]
    candidate = SimpleNamespace(
        candidate_id=str(grounding["proposal_id"]),
        content_hash=str(grounding["raw_candidate_hash"]),
        status="candidate_unbound",
        grounding_disposition=str(grounding["disposition"]),
        candidate_entry_content_hash=str(grounding.get("candidate_entry_content_hash") or ""),
    )
    return problem, candidate, context


@cache
def _run_real_education_value_refusal() -> Any:
    from polisyos.runtime.quality.generation_cycle import (
        FoundryValuePort,
        SimulationPortObservation,
    )

    problem, candidate, context = _education_lane()
    world = context.world_model_record
    simulation = SimulationPortObservation(
        candidate_id=candidate.candidate_id,
        status="joint_simulated",
        simulation_ref=gy_content_hash(
            {"candidate_id": candidate.candidate_id, "lane": "education_value_refusal"}
        ),
        k_world_ref_before=world.content_hash,
        k_world_ref_after=world.content_hash,
        world_model_record=world,
    )
    return FoundryValuePort(
        repo_root=_repo_root(),
        cycle_substrate_context=context,
    )(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=0,
    )


def _contract_probe_signature(*, output_contract: type[object], family: str) -> Any:
    from polisyos.foundry.methods.base import (
        ComplexityClass,
        FidelityLevel,
        MethodSignature,
        SlotSpec,
        SlotType,
        Unit,
    )

    return MethodSignature(
        name="value_projection_contract_probe",
        namespace=f"contract_probe.{family}",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(
            {
                SlotSpec.for_output_contract(
                    "result",
                    SlotType.SCALAR,
                    Unit("value", "json"),
                    output_contract=output_contract,
                )
            }
        ),
        parameters=(),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_1,
        family=family,
    )


def _contract_estimand(parameter: str = "coefficients_0") -> Any:
    from polisyos.foundry.methods.components.consensus import EstimandSpec

    return EstimandSpec(
        query_id="gy-n10-native-value-contract-proof",
        estimand_id=parameter,
        outcome="owner_resolved_outcome",
        treatment_or_exposure="owner_resolved_exposure",
        population="contract_probe_population",
        time_horizon="1",
        unit="value",
        target_role="causal",
    )


def _native_projection_cases() -> tuple[tuple[object, Any, Any], ...]:
    from polisyos.foundry.methods.catalog.bayesian.protocols import PosteriorResult
    from polisyos.foundry.methods.catalog.bayesian.regression import (
        BayesianLinearRegressionEstimator,
    )
    from polisyos.foundry.methods.catalog.econometrics.protocols import EconometricResult
    from polisyos.foundry.methods.catalog.econometrics.timeseries import TimeSeriesEstimator
    from polisyos.ir.analytics.distributional import (
        DistributionalBoundsBundle,
        DistributionalFunctional,
        FunctionalBounds,
        GridAxis,
    )
    from polisyos.ir.analytics.forecasting_uncertainty import (
        FanChartSpec,
        ForecastCalibrationMethod,
        ForecastCoverageDiagnostic,
        ForecastingUncertaintyBundle,
        ForecastIntervalSemantics,
        HorizonInterval,
        HorizonPolicySpec,
    )
    from polisyos.ir.analytics.partial_identification import (
        BoundMethod,
        BoundsBundle,
        PartialIdentificationResult,
    )
    from polisyos.ir.analytics.transportability import (
        TransportabilityResult,
        TransportabilityStatus,
        TransportMode,
    )

    generated_at = datetime(2026, 7, 13, tzinfo=UTC)
    posterior = PosteriorResult(
        method_name="bayesian_linear_regression",
        posterior_means={"coefficients_0": 1.5},
        posterior_stds={"coefficients_0": 0.8},
        credible_intervals={"coefficients_0": (-2.0, 5.0)},
        sampler_family="mcmc",
        diagnostics={
            "credible_mass": 0.9,
            "num_samples": 128,
            "rhat_max": 1.01,
            "ess_bulk_min": 128.0,
            "ess_tail_min": 64.0,
            "quantile_mcse_relative_max": 0.05,
            "divergences": 0.0,
        },
    )
    econometric = EconometricResult(
        method_name="time_series_ols",
        params={"coefficients_0": 2.0},
        std_errors={"coefficients_0": 0.4},
        confidence_intervals={"coefficients_0": (1.1, 2.9)},
        n_obs=64,
    )
    forecast = ForecastingUncertaintyBundle(
        method_fqn="forecasting.contract_probe@1.0.0",
        target_id="owner_resolved_outcome",
        generated_at=generated_at,
        prediction_interval=(
            HorizonInterval(
                horizon=1,
                point=10.0,
                lower=8.0,
                upper=13.0,
                coverage_target=0.9,
                constructor=ForecastCalibrationMethod.CONFORMAL,
                sample_count=64,
            ),
        ),
        fan_chart=FanChartSpec(quantile_levels=(), horizons=()),
        coverage_diagnostic=ForecastCoverageDiagnostic(
            nominal_coverage=0.9,
            empirical_coverage_by_horizon={1: 0.91},
            sample_count_by_horizon={1: 64},
            last_recalibrated_at=generated_at,
        ),
        horizon_policy=HorizonPolicySpec(
            default_method=ForecastCalibrationMethod.CONFORMAL,
            gate_eligible=True,
        ),
        interval_semantics=ForecastIntervalSemantics.CONFORMALIZED_PREDICTION_INTERVAL,
        calibration_method=ForecastCalibrationMethod.CONFORMAL,
        nominal_coverage=0.9,
        sample_size_assumption="owner calibration rows",
    )
    distributional = DistributionalBoundsBundle(
        estimand_type="quantile_shift",
        functional=DistributionalFunctional.QUANTILE_SHIFT,
        axis=GridAxis(axis_name="quantile", values=(0.25, 0.75), unit="probability"),
        consensus_bounds=FunctionalBounds(lower=(-2.0, -1.0), upper=(1.0, 4.0)),
        sharpness_status="outer_approx",
    )
    partial = BoundsBundle(
        estimand_type="ate",
        lower_bound=-0.5,
        upper_bound=1.25,
        consensus_lower=-0.5,
        consensus_upper=1.25,
        sharpness_status="sharp",
    )
    transport = TransportabilityResult(
        query="transported_ate",
        status=TransportabilityStatus.BOUNDED_NON_IDENTIFIED,
        transport_mode=TransportMode.BOUNDS_ONLY,
        partial_identification_result=PartialIdentificationResult(
            method=BoundMethod.TRANSPORT_BOUNDS,
            lower_bound=-1.0,
            upper_bound=2.0,
            confidence=0.8,
            informativeness_threshold=4.0,
        ),
    )
    return (
        (
            posterior,
            BayesianLinearRegressionEstimator.signature,
            _contract_estimand(),
        ),
        (econometric, TimeSeriesEstimator.signature, _contract_estimand()),
        (
            forecast,
            _contract_probe_signature(
                output_contract=ForecastingUncertaintyBundle,
                family="forecasting",
            ),
            replace(_contract_estimand("owner_resolved_outcome"), target_role="prediction"),
        ),
        (
            distributional,
            _contract_probe_signature(
                output_contract=DistributionalBoundsBundle,
                family="distributional",
            ),
            _contract_estimand("quantile_shift"),
        ),
        (
            partial,
            _contract_probe_signature(
                output_contract=BoundsBundle,
                family="partial_identification",
            ),
            _contract_estimand("ate"),
        ),
        (
            transport,
            _contract_probe_signature(
                output_contract=TransportabilityResult,
                family="transport",
            ),
            _contract_estimand("transported_ate"),
        ),
    )


def _contract_method_result(report: object) -> Any:
    from polisyos.core.observability.determinism import DeterminismTier
    from polisyos.foundry.methods.backends.protocol import (
        MethodResult,
        MethodTiming,
        ReproducibilityInfo,
    )
    from polisyos.foundry.methods.base import ComputeBackend

    return MethodResult(
        output={"result": report},
        slot_outputs={"result": report},
        timing=MethodTiming(wall_time_ms=0.0),
        reproducibility=ReproducibilityInfo(
            backend=ComputeBackend.BAYESIAN,
            determinism_tier=DeterminismTier.STATISTICAL,
            seed=42,
        ),
    )


def _projection_binding(report: object, signature: Any, estimand: Any) -> Any:
    from polisyos.ir.analytics.uncertainty import NativeValueEstimandBinding

    report_payload = (
        report.model_dump(mode="json")
        if hasattr(report, "model_dump")
        else {"type": type(report).__name__}
    )
    return NativeValueEstimandBinding.from_estimand(
        estimand=estimand,
        native_contract_id=str(type(report).contract_id),
        producer_method_fqn=signature.fqn,
        projection_input_content_hash=gy_content_hash(
            {"native_report": report_payload, "estimand": asdict(estimand)}
        ),
    )


def _native_projector_contract_proofs() -> list[dict[str, Any]]:
    from polisyos.foundry.methods.components.value_evidence import (
        MethodValueEvidence,
        project_method_value_evidence,
    )

    proofs: list[dict[str, Any]] = []
    for report, signature, estimand in _native_projection_cases():
        evidence = project_method_value_evidence(
            method_signature=signature,
            method_result=_contract_method_result(report),
            estimand=estimand,
            selected_output_slot="result",
            projection_binding=_projection_binding(report, signature, estimand),
        )
        family = (
            evidence.native_projection_capability.projection_kind.value
            if isinstance(evidence, MethodValueEvidence)
            else "unresolved"
        )
        if not isinstance(evidence, MethodValueEvidence):
            raise RuntimeError(f"native_projection_refused:{family}:{evidence}")
        interval = tuple(evidence.envelope.confidence_interval or ())
        payload = {
            "family": family,
            "proof_scope": "contract_owner_probe_not_advisor_selection",
            **evidence.model_dump(mode="json"),
            "native_interval_width": (interval[1] - interval[0] if len(interval) == 2 else None),
        }
        proofs.append({**payload, "proof_content_hash": gy_content_hash(payload)})
    return proofs


def _projector_refusal_proofs() -> list[dict[str, Any]]:
    from polisyos.core.observability.truthfulness import (
        TruthfulnessReceipt,
        TruthfulnessScope,
        TruthfulnessTier,
    )
    from polisyos.foundry.methods.base import (
        ComplexityClass,
        FidelityLevel,
        MethodSignature,
        SlotSpec,
        SlotType,
        Unit,
    )
    from polisyos.foundry.methods.catalog.bayesian.protocols import PosteriorResult
    from polisyos.foundry.methods.catalog.bayesian.regression import (
        BayesianLinearRegressionEstimator,
    )
    from polisyos.foundry.methods.components.value_evidence import (
        MethodValueRefusal,
        project_method_value_evidence,
    )

    verified = _native_projection_cases()[0]
    verified_report, verified_signature, verified_estimand = verified
    binding = _projection_binding(verified_report, verified_signature, verified_estimand)
    wrong_estimand = replace(
        verified_estimand,
        treatment_or_exposure="caller_fabricated_exposure",
    )
    unverified = PosteriorResult(
        method_name="bayesian_linear_regression",
        posterior_means={"coefficients_0": 1.5},
        posterior_stds={"coefficients_0": 0.8},
        credible_intervals={"coefficients_0": (-2.0, 5.0)},
        diagnostics={"credible_mass": 0.9, "num_samples": 128},
        truthfulness_receipt=TruthfulnessReceipt(
            runtime_truthfulness_tier=TruthfulnessTier.UNVERIFIED,
            truthfulness_scope=TruthfulnessScope.POSTERIOR,
            degradation_reasons=("runtime_calibration_evidence_missing",),
        ),
    )
    unverified_binding = _projection_binding(
        unverified,
        BayesianLinearRegressionEstimator.signature,
        verified_estimand,
    )
    undeclared_signature = MethodSignature(
        name="undeclared_value_contract",
        namespace="contract_probe.refusal",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset({SlotSpec("result", SlotType.SCALAR, Unit("value", "json"))}),
        parameters=(),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_1,
    )
    cases = (
        (
            "unverified_truthfulness",
            project_method_value_evidence(
                method_signature=BayesianLinearRegressionEstimator.signature,
                method_result=_contract_method_result(unverified),
                estimand=verified_estimand,
                selected_output_slot="result",
                projection_binding=unverified_binding,
            ),
        ),
        (
            "wrong_treatment_identity",
            project_method_value_evidence(
                method_signature=verified_signature,
                method_result=_contract_method_result(verified_report),
                estimand=wrong_estimand,
                selected_output_slot="result",
                projection_binding=binding,
            ),
        ),
        (
            "undeclared_capability",
            project_method_value_evidence(
                method_signature=undeclared_signature,
                method_result=_contract_method_result(verified_report),
                estimand=verified_estimand,
                selected_output_slot="result",
            ),
        ),
    )
    output: list[dict[str, Any]] = []
    for case_id, refusal in cases:
        if not isinstance(refusal, MethodValueRefusal):
            raise RuntimeError(f"projector_refusal_case_auto_passed:{case_id}")
        payload = {"case_id": case_id, **refusal.model_dump(mode="json")}
        output.append({**payload, "proof_content_hash": gy_content_hash(payload)})
    return output


@cache
def _unseen_transport_lane() -> tuple[DesignProblem, object, Any]:
    """Build one content-bound water-quality transport input from pack-shaped data."""

    from polisyos.runtime.quality.cycle_substrate import (
        TransportContextEvidence,
        TransportCovariateObservation,
        build_cycle_substrate_context,
        cycle_substrate_context_binding_hash,
    )
    from polisyos.runtime.quality.generation_cycle import (
        _build_boundary_world_model_record,
    )

    problem = DesignProblem(
        design_problem_id="water_quality_transport_problem",
        problem_statement=(
            "Estimate how a riparian buffer changes nitrate load across watersheds."
        ),
        domain="water_quality",
        nl_provenance=NLProvenance(
            raw_request=("Estimate how a riparian buffer changes nitrate load across watersheds."),
            source_surface="gy_n8_unseen_pack_transport_probe",
        ),
        authority_profile=AuthorityProfile(
            requester_authority="quality_audit",
            requested_authority_level="research",
            mandate="Exercise the generic transport owner on unseen pack-shaped data.",
        ),
        jurisdiction_time=JurisdictionTimeSemantics(
            region="watershed_target",
            valid_time="2024/2025",
            as_of="2026-07-06T00:00:00+00:00",
            policy_time="2025",
            data_time="2024/2025",
        ),
        objectives=[
            DesignObjective(
                objective_id="reduce_nitrate_load",
                description="Reduce nitrate load in the target watershed.",
                metric_id="nitrate_load",
            )
        ],
        stakeholders=[
            DesignStakeholder(
                stakeholder_id="watershed_communities",
                name="Watershed communities",
                role="affected_population",
            )
        ],
        outcome_of_interest=OutcomeOfInterest(
            target_variable="nitrate_load",
            metric_id="nitrate_load",
            estimand="average_treatment_effect",
        ),
        candidate_lever_space=CandidateLeverSpace(
            allowed_operator_kinds=["buffer_width"],
            candidate_levers=[
                CandidateLever(
                    lever_id="riparian_buffer_width",
                    operator_kind="buffer_width",
                    instrument="water_quality.riparian_buffer_width",
                    target_slot="nitrate_load",
                )
            ],
        ),
        evidence_acquisition_needs=EvidenceAcquisitionNeeds(),
        runtime_hints={},
    )
    registry = _audit_registry()
    selected_hashes = tuple(entry.entry_content_hash for entry in registry.entries)
    world = _build_boundary_world_model_record(
        repo_root=_repo_root(),
        problem=problem,
        outcome="nitrate_load",
        policy_slot_ids=("nitrate_load",),
        substrate_registry=registry,
        selected_registry_entry_hashes=selected_hashes,
    )
    measurements = {
        "canonical_var": "watershed_slope",
        "source": {
            "context_id": "water_quality:source_watershed",
            "value": 0.15,
            "evidence_ref": "lane0://water_quality/source/watershed_slope",
        },
        "target": {
            "context_id": "water_quality:target_watershed",
            "value": 0.63,
            "evidence_ref": "lane0://water_quality/target/watershed_slope",
        },
    }
    source_row = {
        "canonical_var": measurements["canonical_var"],
        **measurements["source"],
    }
    target_row = {
        "canonical_var": measurements["canonical_var"],
        **measurements["target"],
    }
    source_row_hash = gy_content_hash(source_row)
    target_row_hash = gy_content_hash(target_row)
    source_profile_hash = gy_content_hash((source_row,))
    target_profile_hash = gy_content_hash((target_row,))
    substrate_input = {
        "schema_version": "policyos.layer3.gy.n8.pack_shaped_transport_input.v1",
        "domain": problem.domain,
        "registry_content_hash": registry.content_hash,
        "world_model_record_content_hash": world.content_hash,
        "measurements": measurements,
    }
    substrate_input_hash = gy_content_hash(substrate_input)
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    binding_hash = cycle_substrate_context_binding_hash(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_input_content_hash=substrate_input_hash,
        substrate_registry_content_hash=registry.content_hash,
        world_model_record_id=world.world_model_record_id,
        world_model_record_content_hash=world.content_hash,
        world_model_record_authority_status=world.authority_status,
        selected_registry_entry_hashes=selected_hashes,
    )
    transport_context = TransportContextEvidence(
        status="candidate_context_only_not_transport_authority",
        source_context_id=str(measurements["source"]["context_id"]),
        target_context_id=str(measurements["target"]["context_id"]),
        source_profile_content_hash=source_profile_hash,
        target_profile_content_hash=target_profile_hash,
        substrate_input_content_hash=substrate_input_hash,
        context_binding_hash=binding_hash,
        covariates=(
            TransportCovariateObservation(
                canonical_var=str(measurements["canonical_var"]),
                source_value=float(measurements["source"]["value"]),
                target_value=float(measurements["target"]["value"]),
                source_row_content_hash=source_row_hash,
                target_row_content_hash=target_row_hash,
            ),
        ),
    )
    context = build_cycle_substrate_context(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_registry=registry,
        selected_registry_entry_hashes=selected_hashes,
        world_model_record=world,
        intervention_substrate=None,
        candidate_levers=(),
        transport_context=transport_context,
        source_pack_content_hash=gy_content_hash(substrate_input),
        substrate_input_content_hash=substrate_input_hash,
    )
    candidate = SimpleNamespace(
        candidate_id="riparian_buffer_candidate",
        treatment_variable="riparian_buffer_width",
        atom=SimpleNamespace(
            intervention_id="water_quality.riparian_buffer_width",
            target_world_slots=("nitrate_load",),
        ),
    )
    return problem, candidate, context


def _transport_component_proof(
    *,
    domain_role: str,
    problem: DesignProblem,
    candidate: object,
    context: Any,
    data_owner: str,
    context_source: str,
) -> dict[str, Any]:
    from polisyos.runtime.quality.generation_cycle import (
        RealValueOwnerGateway,
        ValueOwnerAccessError,
        _candidate_content_hash,
        _candidate_transport_outcome_variable,
        _candidate_transport_treatment_variable,
        _run_value_transport,
    )

    query_treatment = _candidate_transport_treatment_variable(candidate)
    query_outcome = _candidate_transport_outcome_variable(candidate, problem)
    candidate_id = str(getattr(candidate, "candidate_id", "") or "")
    if hasattr(candidate, "model_dump"):
        candidate_payload = candidate.model_dump(mode="json")
    elif hasattr(candidate, "__dataclass_fields__"):
        candidate_payload = asdict(candidate)
    else:
        atom = getattr(candidate, "atom", None)
        candidate_payload = {
            "candidate_id": candidate_id,
            "treatment_variable": getattr(candidate, "treatment_variable", None),
            "atom": {
                "intervention_id": getattr(atom, "intervention_id", None),
                "target_world_slots": list(getattr(atom, "target_world_slots", ()) or ()),
            },
        }
    gateway = RealValueOwnerGateway(
        repo_root=_repo_root(),
        cycle_substrate_context=context,
    )
    transport = context.transport_context
    covariates = (
        []
        if transport is None
        else [observation.model_dump(mode="json") for observation in transport.covariates]
    )
    common = {
        "schema_version": "policyos.layer3.gy.n8.transport_component_proof.v1",
        "rule_version": "policyos.layer3.gy.n8.transport_context.v2",
        "domain_role": domain_role,
        "domain": problem.domain,
        "design_problem_ref": gy_content_hash(problem.model_dump(mode="json")),
        "candidate_id": candidate_id,
        "candidate_content_hash": _candidate_content_hash(candidate),
        "candidate_envelope_content_hash": gy_content_hash(candidate_payload),
        "component_scope_only": True,
        "production_value_eligible": False,
        "data_owner": data_owner,
        "context_source": context_source,
        "cycle_substrate_context_content_hash": context.content_hash,
        "context_binding_hash": context.context_binding_hash,
        "world_model_record_id": context.world_model_record.world_model_record_id,
        "world_model_record_content_hash": context.world_model_record.content_hash,
        "transport_covariates": covariates,
        "query_treatment": query_treatment,
        "query_outcome": query_outcome,
        "value_gate_receipt": None,
    }
    try:
        inputs = gateway.build_transport_inputs(
            candidate=candidate,
            problem=problem,
            world_record=context.world_model_record,
        )
    except ValueOwnerAccessError as exc:
        payload = {
            **common,
            "outcome_kind": "typed_refusal",
            "required_target_data": [],
            "selection_diagram_content_hash": None,
            "selection_nodes": [],
            "transport_receipt": None,
            "transport_result_content_hash": None,
            "typed_refusal": {
                "code": exc.code,
                "reason": str(exc),
                "owner_access_ref": exc.owner_access_ref,
            },
        }
        return {**payload, "proof_content_hash": gy_content_hash(payload)}

    diagram = inputs["selection_diagram"]
    result, error = _run_value_transport(
        inputs=inputs,
        world_record=context.world_model_record,
    )
    selection_nodes = [
        {
            "target_variable": node.target_variable,
            "source_ref": node.source_ref,
            "target_ref": node.target_ref,
            "source_value": node.source_value,
            "target_value": node.target_value,
        }
        for node in diagram.s_nodes
    ]
    if result is None:
        payload = {
            **common,
            "outcome_kind": "typed_refusal",
            "required_target_data": [],
            "selection_diagram_content_hash": gy_content_hash(diagram.model_dump(mode="json")),
            "selection_nodes": selection_nodes,
            "transport_receipt": None,
            "transport_result_content_hash": None,
            "typed_refusal": {
                "code": str(error or "transport_solver_refused").split(":", 1)[0],
                "reason": str(error or "transport solver refused"),
                "owner_access_ref": None,
            },
        }
        return {**payload, "proof_content_hash": gy_content_hash(payload)}

    receipt_payload = result.model_dump(mode="json")
    payload = {
        **common,
        "outcome_kind": "transport_receipt",
        "required_target_data": list(result.required_target_data),
        "selection_diagram_content_hash": gy_content_hash(diagram.model_dump(mode="json")),
        "selection_nodes": selection_nodes,
        "transport_receipt": receipt_payload,
        "transport_result_content_hash": gy_content_hash(receipt_payload),
        "typed_refusal": None,
    }
    return {**payload, "proof_content_hash": gy_content_hash(payload)}


def _transport_component_proofs() -> dict[str, Any]:
    first_lane = _canonical_first_vertical_lane()
    education_problem, education_candidate, education_context = _education_lane()
    education_entry_hash = str(getattr(education_candidate, "candidate_entry_content_hash", ""))
    education_lever = next(
        (
            lever
            for lever in education_context.candidate_levers
            if lever.entry_content_hash == education_entry_hash
        ),
        None,
    )
    if education_lever is None:
        raise RuntimeError("education_transport_candidate_lever_unresolved")
    unseen_problem, unseen_candidate, unseen_context = _unseen_transport_lane()
    return {
        "first_vertical": _transport_component_proof(
            domain_role="first_vertical",
            problem=first_lane["problem"],
            candidate=first_lane["candidate"],
            context=first_lane["cycle_substrate_context"],
            data_owner="L1_DCAT_ds_observations",
            context_source="canonical_first_vertical_cycle_substrate_context",
        ),
        "education": _transport_component_proof(
            domain_role="education",
            problem=education_problem,
            candidate=education_candidate,
            context=education_context,
            data_owner="N10a_pack_transport_context",
            context_source="content_bound_pack_cycle_substrate_context",
        ),
        "unseen_pack_shape": _transport_component_proof(
            domain_role="unseen_pack_shape",
            problem=unseen_problem,
            candidate=unseen_candidate,
            context=unseen_context,
            data_owner="pack_shaped_lane0_measurements",
            context_source="content_bound_unseen_pack_shape",
        ),
    }


def _receipt_payload(
    identification_status: str,
    *,
    lower: tuple[float, ...],
    upper: tuple[float, ...],
    transport_status: str,
    forecast_tier: str = "observable_calibrated",
    transport_mode: str = "direct",
) -> dict[str, Any]:
    world = _audit_world_record()
    value_set = _value_set(
        identification_status,
        lower=lower,
        upper=upper,
        forecast_tier=forecast_tier,
        transport_status=transport_status,
        transport_mode=transport_mode,
    )
    transport = _transport_receipt(
        world_record=world,
        status="transported_limited" if transport_mode != "direct" else "direct",
        transport_status=transport_status,
        transport_mode=transport_mode,
    )
    calibration = _calibration_receipt(forecast_tier=forecast_tier)
    candidate_id = (
        "candidate_live_value"
        if identification_status == "point"
        else f"candidate_{identification_status}"
    )
    selected_method_fqn = "causal.inference.synthetic_control@1.0.0"
    value_ref = gy_content_hash(
        {
            "candidate_id": candidate_id,
            "world_model_record_content_hash": world.content_hash,
            "method_fqn": selected_method_fqn,
            "value_outer_set": value_set.canonical_payload(),
            "transport_receipt": transport.model_dump(mode="json"),
            "calibration_receipt": calibration.model_dump(mode="json"),
        }
    )
    receipt = ValueGateReceipt(
        candidate_id=candidate_id,
        evaluation_mode="simulate_only",
        selected_method_fqn=selected_method_fqn,
        method_selection_trace=(),
        identification_status=identification_status,  # type: ignore[arg-type]
        value_outer_set=value_set,
        transport_receipt=transport,
        calibration_receipt=calibration,
        world_model_record_id=world.world_model_record_id,
        world_model_record_content_hash=world.content_hash,
        value_ref=value_ref,
        wall_time_ms=0.0,
        wmr_cache_status="built",
        k_world_ref_before=world.content_hash,
        k_world_ref_after=world.content_hash,
    )
    return {
        **receipt.model_dump(mode="json"),
        "value_outer_set_width_derived": list(value_set.width),
    }


def _value_set(
    identification_status: str,
    *,
    lower: tuple[float, ...],
    upper: tuple[float, ...],
    forecast_tier: str = "observable_calibrated",
    transport_status: str = "identified",
    transport_mode: str = "direct",
) -> ValueOuterSet:
    world = _audit_world_record()
    return ValueOuterSet.interval_box(
        coordinates=("CausalMethod.SYNTHETIC_CONTROL",),
        lower=lower,
        upper=upper,
        identification_mode=identification_status,
        assumptions=(
            "foundry_method_output",
            f"transport:{transport_status}",
            f"forecast_tier:{forecast_tier}",
        ),
        assumption_status="externally_supported",
        calibration_scope={
            "forecast_tier": forecast_tier,
            "transport_status": transport_status,
            "transport_mode": transport_mode,
        },
        data_trust=DataTrust(
            tier="simulate_only_shadow",
            trust_cap=0.6,
            trust_multiplier=0.6,
            min_coverage=0.0,
            max_coverage=1.0,
            promotion_floor=0.5,
            authority_ref="policyos.runtime.n8.simulate_only_shadow",
        ),
        world_model_record_ref=world.content_hash,
        epoch=world.valid_time_scope,
        representation_status="certified",
    )


def _transport_receipt(
    *,
    world_record: Any | None = None,
    status: str = "direct",
    transport_status: str = "identified",
    transport_mode: str = "direct",
) -> ValueTransportReceipt:
    world = world_record or _audit_world_record()
    return ValueTransportReceipt(
        status=status,  # type: ignore[arg-type]
        world_model_record_id=world.world_model_record_id,
        world_model_record_content_hash=world.content_hash,
        transport_result_ref=(
            "sha256:048137f39d3435c8ef094949d8979b3576116ccc3d2c6618e26a2756b2f096db"
            if status == "direct"
            and transport_status == "identified"
            and transport_mode == "direct"
            else gy_content_hash({"transport_status": transport_status})
        ),
        transport_status=transport_status,
        transport_mode=transport_mode,
        identification_engine=(
            "simplified_legacy"
            if status == "direct"
            and transport_status == "identified"
            and transport_mode == "direct"
            else "transport_engine"
        ),
        required_target_data=(),
        limitation_refs=(),
    )


def _calibration_receipt(
    *,
    status: str = "pass",
    forecast_tier: str = "observable_calibrated",
) -> ValueCalibrationReceipt:
    live_s10_report_ref = "sha256:69bf8fad7fe2f1149ac628b8855410c70ea777f39bfaa4bfae8ce8a5ef3edd88"
    return ValueCalibrationReceipt(
        status=status,  # type: ignore[arg-type]
        forecast_tier=forecast_tier,
        calibration_record_ref=(
            f"s10://n8/{live_s10_report_ref.removeprefix('sha256:')}/calibration"
        ),
        uncertainty_interval_refs=(f"interval://{live_s10_report_ref}/95",),
        false_clear_counts={},
        issue_codes=(),
    )


def _mutation_expectations() -> list[dict[str, Any]]:
    """Return declarative cases; only the live harness may report observed REDs."""

    return [
        {
            "mutation_id": mutation_id,
            "expected_result": "RED",
            "proof": FROZEN_MUTATION_PROOFS[mutation_id],
        }
        for mutation_id in EXPECTED_MUTATION_IDS
    ]


def _live_mutation_results(repo_root: Path) -> list[dict[str, Any]]:
    probes = {
        "value_input_read_from_runtime_hint": lambda: _probe_no_value_runtime_hint_reads(repo_root),
        "empty_hints_production_owner_access": _probe_empty_hints_owner_access,
        "audit_value_solve_fed_by_test_hints": _probe_audit_not_fed_by_hints,
        "wmr_unavailable_not_acquire_gap": _probe_missing_wmr_is_wiring_error,
        "value_outer_set_width_supplied_not_derived": _probe_supplied_width_rejected,
        "persisted_width_verification_removed": _probe_persisted_width_tamper_rejected,
        "proxy_forecast_narrow_set_rejected": _probe_proxy_narrow_rejected,
        "fixture_world_model_hash_rejected": _probe_fixture_world_hash_rejected,
        "value_world_version_laundered": _probe_world_laundering_rejected,
        "dominance_timeout_forced_not_unknown": _probe_timeout_unknown,
        "simulate_only_shrank_k_world": _probe_simulate_only_shrink_rejected,
        "bad_forecast_minted_value": _probe_bad_forecast_cases_blocked,
        "pilot_mode_ran_without_eval_safety": _probe_mode_gates_block,
        "value_method_selection_fixed_default": _probe_selection_not_fixed_default,
        "value_blocked_candidate_promoted_to_decision_front": _probe_value_blocks_promotion,
    }
    results = []
    for mutation_id, probe in probes.items():
        try:
            detail = probe()
            results.append(
                {
                    "mutation_id": mutation_id,
                    "result": "RED",
                    "proof": detail,
                }
            )
        except Exception as exc:  # pragma: no cover - validator emits this as data.
            results.append(
                {
                    "mutation_id": mutation_id,
                    "result": "GREEN_MUTATION_SURVIVED",
                    "proof": str(exc),
                }
            )
    return results


@dataclass(frozen=True)
class _SourceFlipReplacement:
    relative_path: str
    old: str
    new: str


@dataclass(frozen=True)
class _SourceFlipCase:
    mutation_id: str
    guard: str
    replacements: tuple[_SourceFlipReplacement, ...]
    probe_command: tuple[str, ...]
    expected_red_patterns: tuple[str, ...]


def run_source_flip_mutations(repo_root: Path) -> tuple[dict[str, Any], ...]:
    """Temporarily remove runtime guards and require the targeted probe to go RED."""

    _ensure_src_path(repo_root)
    cases = _source_flip_cases()
    observed_ids = tuple(case.mutation_id for case in cases)
    results: list[dict[str, Any]] = []
    if observed_ids != SOURCE_FLIP_MUTATION_IDS:
        results.append(
            {
                "mutation_id": "source_flip_harness_denominator",
                "result": "HARNESS_ERROR",
                "proof": {
                    "expected": list(SOURCE_FLIP_MUTATION_IDS),
                    "observed": list(observed_ids),
                },
            }
        )
        return tuple(results)
    touched_paths = tuple(
        sorted(
            {
                repo_root / replacement.relative_path
                for case in cases
                for replacement in case.replacements
            },
            key=lambda path: path.as_posix(),
        )
    )
    suite_hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in touched_paths}
    baseline_by_command: dict[tuple[str, ...], dict[str, Any]] = {}
    for case in cases:
        if case.probe_command in baseline_by_command:
            continue
        completed = subprocess.run(
            case.probe_command,
            cwd=repo_root,
            text=True,
            capture_output=True,
            timeout=900,
            check=False,
        )
        baseline_by_command[case.probe_command] = {
            "exit_code": completed.returncode,
            "stdout_tail": _output_tail(completed.stdout),
            "stderr_tail": _output_tail(completed.stderr),
        }
        if completed.returncode != 0:
            return (
                {
                    "mutation_id": case.mutation_id,
                    "result": "BASELINE_ERROR",
                    "guard": case.guard,
                    "proof": {
                        "command": list(case.probe_command),
                        **baseline_by_command[case.probe_command],
                    },
                },
            )
    for case in cases:
        result = _run_source_flip_case(repo_root, case)
        restored_suite_hashes = {
            path: hashlib.sha256(path.read_bytes()).hexdigest() for path in touched_paths
        }
        mismatches = [
            path.relative_to(repo_root).as_posix()
            for path in touched_paths
            if restored_suite_hashes[path] != suite_hashes[path]
        ]
        if mismatches:
            result = {
                "mutation_id": case.mutation_id,
                "result": "RESTORE_ERROR",
                "guard": case.guard,
                "proof": {"suite_restoration_mismatch": mismatches},
            }
        else:
            result["baseline"] = baseline_by_command[case.probe_command]
            result["suite_source_restored_sha256"] = {
                path.relative_to(repo_root).as_posix(): restored_suite_hashes[path]
                for path in touched_paths
            }
        results.append(result)
        if result.get("result") != "RED":
            break
    return tuple(results)


def _run_source_flip_case(repo_root: Path, case: _SourceFlipCase) -> dict[str, Any]:
    originals: dict[Path, bytes] = {}
    original_hashes: dict[Path, str] = {}
    result: dict[str, Any]
    try:
        for replacement in case.replacements:
            path = repo_root / replacement.relative_path
            if path not in originals:
                original = path.read_bytes()
                originals[path] = original
                original_hashes[path] = hashlib.sha256(original).hexdigest()
            text = path.read_text(encoding="utf-8")
            target_count = text.count(replacement.old)
            if target_count != 1:
                result = {
                    "mutation_id": case.mutation_id,
                    "result": "MUTATION_TARGET_ERROR",
                    "guard": case.guard,
                    "proof": {
                        "relative_path": replacement.relative_path,
                        "expected_target_count": 1,
                        "observed_target_count": target_count,
                    },
                }
                break
            path.write_text(
                text.replace(replacement.old, replacement.new, 1),
                encoding="utf-8",
            )
        else:
            completed = subprocess.run(
                case.probe_command,
                cwd=repo_root,
                text=True,
                capture_output=True,
                timeout=900,
                check=False,
            )
            combined_output = f"{completed.stdout}\n{completed.stderr}"
            if completed.returncode == 0:
                result = {
                    "mutation_id": case.mutation_id,
                    "result": "GREEN_MUTATION_SURVIVED",
                    "guard": case.guard,
                    "proof": {
                        "command": list(case.probe_command),
                        "stdout_tail": _output_tail(completed.stdout),
                        "stderr_tail": _output_tail(completed.stderr),
                    },
                }
            elif completed.returncode == 1 and all(
                pattern in combined_output for pattern in case.expected_red_patterns
            ):
                result = {
                    "mutation_id": case.mutation_id,
                    "result": "RED",
                    "guard": case.guard,
                    "proof": {
                        "command": list(case.probe_command),
                        "exit_code": completed.returncode,
                        "expected_red_patterns": list(case.expected_red_patterns),
                        "stdout_tail": _output_tail(completed.stdout),
                        "stderr_tail": _output_tail(completed.stderr),
                    },
                }
            else:
                result = {
                    "mutation_id": case.mutation_id,
                    "result": "PROBE_ERROR",
                    "guard": case.guard,
                    "proof": {
                        "command": list(case.probe_command),
                        "exit_code": completed.returncode,
                        "expected_red_patterns": list(case.expected_red_patterns),
                        "stdout_tail": _output_tail(completed.stdout),
                        "stderr_tail": _output_tail(completed.stderr),
                    },
                }
    except Exception as exc:  # pragma: no cover - reported as harness data.
        result = {
            "mutation_id": case.mutation_id,
            "result": "PROBE_ERROR",
            "guard": case.guard,
            "proof": str(exc),
        }
    finally:
        for path, original in originals.items():
            path.write_bytes(original)

    restoration_errors = []
    restored_hashes = {}
    for path, original in originals.items():
        restored = path.read_bytes()
        restored_hash = hashlib.sha256(restored).hexdigest()
        restored_hashes[str(path.relative_to(repo_root))] = restored_hash
        if restored != original or restored_hash != original_hashes[path]:
            restoration_errors.append(str(path.relative_to(repo_root)))
    if restoration_errors:
        return {
            "mutation_id": case.mutation_id,
            "result": "RESTORE_ERROR",
            "guard": case.guard,
            "proof": {
                "restoration_mismatch": restoration_errors,
                "source_restored_sha256": restored_hashes,
            },
        }
    result["source_restored_sha256"] = restored_hashes
    return result


def _output_tail(output: str, *, max_lines: int = 20) -> str:
    lines = [line for line in output.splitlines() if line.strip()]
    return "\n".join(lines[-max_lines:])


def _pytest_probe(*node_ids: str) -> tuple[str, ...]:
    return (sys.executable, "-m", "pytest", *node_ids, "-q")


def _python_probe(script: str) -> tuple[str, ...]:
    return (sys.executable, "-c", script)


def _validator_probe(*args: str) -> tuple[str, ...]:
    return (
        sys.executable,
        "tools/quality/validation/check_layer3_gy_value_gate_contract.py",
        *args,
    )


def _source_flip_cases() -> tuple[_SourceFlipCase, ...]:
    discovery = "src/polisyos/core/components/discovery.py"
    generation_cycle = "src/polisyos/runtime/quality/generation_cycle.py"
    value_outer_set = "src/polisyos/core/contracts/value_outer_set.py"
    validator = "tools/quality/validation/check_layer3_gy_value_gate_contract.py"
    advisor = "src/polisyos/foundry/methods/selection/advisor.py"
    value_evidence = "src/polisyos/foundry/methods/components/value_evidence.py"
    uncertainty = "src/polisyos/ir/analytics/uncertainty.py"
    cycle_substrate = "src/polisyos/runtime/quality/cycle_substrate.py"
    world_model_record = "src/polisyos/runtime/quality/world_model_record.py"
    test_value_gate = "tests/unit/runtime/quality/test_value_gate.py"
    test_generation_cycle = "tests/unit/runtime/quality/test_generation_cycle.py"

    def pytest_case(
        *,
        mutation_id: str,
        guard: str,
        replacements: tuple[_SourceFlipReplacement, ...],
        node_id: str,
    ) -> _SourceFlipCase:
        return _SourceFlipCase(
            mutation_id=mutation_id,
            guard=guard,
            replacements=replacements,
            probe_command=_pytest_probe(node_id),
            expected_red_patterns=(node_id.rsplit("::", 1)[-1].split("[", 1)[0], "FAILED"),
        )

    return (
        pytest_case(
            mutation_id="source_flip_value_input_read_from_runtime_hint",
            guard="runtime value hints cannot change an owner-derived terminal",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    (
                        "        inputs = self._selection_inputs()\n"
                        "        mode = self._evaluation_mode\n"
                    ),
                    (
                        "        inputs = self._selection_inputs()\n"
                        "        mode = self._evaluation_mode\n"
                        '        if _mapping(_object_get(problem, "runtime_hints")).get(\n'
                        '            "value_gate_inputs"\n'
                        "        ) is not None:\n"
                        "            return _blocked_value_observation(\n"
                        '                code="source_flip_runtime_value_hint_trusted",\n'
                        '                reason="source flip trusted caller value hints",\n'
                        "                mode=mode,\n"
                        "                started=started,\n"
                        "                candidate_id=candidate_id,\n"
                        "            )\n"
                    ),
                ),
            ),
            node_id=(
                f"{test_value_gate}::test_runtime_value_hints_cannot_change_owner_data_terminal"
            ),
        ),
        pytest_case(
            mutation_id="source_flip_empty_hints_production_owner_access",
            guard="empty-hints production path reaches the real substrate owner",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    (
                        "        try:\n"
                        "            method_state = self._owner_gateway.load_value_data_profile(\n"
                    ),
                    (
                        "        try:\n"
                        "            raise ValueOwnerAccessError(\n"
                        '                "value_method_state_missing",\n'
                        '                "source flip bypassed real owner access",\n'
                        "            )\n"
                        "            method_state = self._owner_gateway.load_value_data_profile(\n"
                    ),
                ),
            ),
            node_id=(
                f"{test_value_gate}::"
                "test_production_value_block_is_real_data_gap_not_missing_inputs"
            ),
        ),
        pytest_case(
            mutation_id="source_flip_audit_value_solve_fed_by_test_hints",
            guard="frozen first-vertical replay uses the content-bound N4 DesignProblem",
            replacements=(
                _SourceFlipReplacement(
                    validator,
                    (
                        "def _run_real_first_vertical_cycle() -> Any:\n"
                        '    """Replay the real N4 result through N6/N5/N8 and the canonical N7 router."""\n'
                    ),
                    (
                        "def _run_real_first_vertical_cycle() -> Any:\n"
                        '    """Replay the real N4 result through N6/N5/N8 and the canonical N7 router."""\n'
                        "    _source_flip_problem = _audit_problem()\n"
                    ),
                ),
                _SourceFlipReplacement(
                    validator,
                    '    lane = _canonical_first_vertical_lane()\n    expected_problem_ref = gy_content_hash(lane["problem"].model_dump(mode="json"))\n',
                    '    lane = {**_canonical_first_vertical_lane(), "problem": _source_flip_problem}\n    expected_problem_ref = gy_content_hash(lane["problem"].model_dump(mode="json"))\n',
                ),
            ),
            node_id=(
                f"{test_value_gate}::"
                "test_n8_first_vertical_real_cycle_routes_owner_data_gap_through_n7"
            ),
        ),
        pytest_case(
            mutation_id="source_flip_wmr_unavailable_not_acquire_gap",
            guard="missing cycle WMR is controller wiring, not acquire_data",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    '                code=world_error or "value_world_model_record_unwired",\n',
                    '                code="acquire_data:value_world_model_record_missing",\n',
                ),
            ),
            node_id=f"{test_value_gate}::test_missing_cycle_wmr_is_wiring_error_not_acquire_gap",
        ),
        pytest_case(
            mutation_id="source_flip_s10_owner_invocation_required",
            guard="real S10 build_forecast_support invocation must run before value mints",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "    support = build_forecast_support(\n",
                    (
                        '    raise RuntimeError("source_flip_s10_owner_not_invoked")\n'
                        "    support = build_forecast_support(\n"
                    ),
                ),
            ),
            node_id=f"{test_value_gate}::test_s10_refusal_is_report_driven_by_bad_did_report",
        ),
        pytest_case(
            mutation_id="source_flip_calibration_report_driven_refusal",
            guard="S10 evidence is derived from report diagnostics and can refuse",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "        and diagnostics_pass\n        and treated > 0\n",
                    "        and treated > 0\n",
                ),
            ),
            node_id=f"{test_value_gate}::test_s10_refusal_is_report_driven_by_bad_did_report",
        ),
        pytest_case(
            mutation_id="source_flip_width_tracks_real_did_ci",
            guard="partial ValueOuterSet lower/upper come from the real DID confidence interval",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "        lower = lower_ci\n        upper = upper_ci\n",
                    "        lower = upper = point_value\n",
                ),
            ),
            node_id=f"{test_value_gate}::test_partial_value_outer_set_width_tracks_real_did_interval",
        ),
        pytest_case(
            mutation_id="source_flip_transport_real_solver_required",
            guard="transport receipt is produced by solve_transportability over the candidate diagram",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "        result = solve_transportability(\n",
                    (
                        '        raise RuntimeError("source_flip_transport_disabled")\n'
                        "        result = solve_transportability(\n"
                    ),
                ),
            ),
            node_id=f"{test_value_gate}::test_unseen_transport_receipt_uses_real_solver_contract",
        ),
        pytest_case(
            mutation_id="source_flip_transport_tuple_reintroduced",
            guard="transport vocabulary comes only from the content-bound context",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    (
                        "    transport_covariates = tuple(\n"
                        "        observation.canonical_var for observation in "
                        "transport.covariates\n"
                        "    )\n"
                    ),
                    ('    transport_covariates = ("state_capacity", "institutional_quality")\n'),
                ),
            ),
            node_id=f"{test_value_gate}::test_education_selection_diagram_uses_only_pack_covariates",
        ),
        pytest_case(
            mutation_id="source_flip_transport_measured_values_removed",
            guard="selection S-nodes retain owner-measured source and target values",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "            source_value=observation.source_value,\n",
                    "            source_value=0.0,\n",
                ),
            ),
            node_id=f"{test_value_gate}::test_third_pack_transport_vocabulary_flows_without_engine_change",
        ),
        pytest_case(
            mutation_id="source_flip_treatment_candidate_atom_binding_required",
            guard="candidate treatment-shaped fields cannot alter owner rows",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "        return profile\n",
                    (
                        '        if _object_get(candidate, "treated_unit_ids") or _object_get(\n'
                        '            _object_get(candidate, "atom"), "treated_unit_ids"\n'
                        "        ):\n"
                        "            return profile.model_copy(\n"
                        '                update={"owner_access_ref": "candidate://source-flip"}\n'
                        "            )\n"
                        "        return profile\n"
                    ),
                ),
            ),
            node_id=f"{test_value_gate}::test_shaped_owner_assignment_attestation_is_not_authority",
        ),
        pytest_case(
            mutation_id="source_flip_value_outer_set_width_supplied_not_derived",
            guard="ValueOuterSet rejects caller-supplied width",
            replacements=(
                _SourceFlipReplacement(
                    value_outer_set,
                    '        raise ValueError("value_outer_set_width_supplied_not_derived")\n',
                    (
                        "        payload = dict(data)\n"
                        '        payload.pop("width", None)\n'
                        "        return payload\n"
                    ),
                ),
            ),
            node_id=f"{test_value_gate}::test_hand_set_value_outer_set_width_is_rejected",
        ),
        pytest_case(
            mutation_id="source_flip_persisted_width_verification_removed",
            guard="persisted ValueOuterSet width checksum is verified before re-derivation",
            replacements=(
                _SourceFlipReplacement(
                    value_outer_set,
                    "        if persisted_width != expected_width:\n",
                    "        if False and persisted_width != expected_width:\n",
                ),
            ),
            node_id=(
                "tests/unit/core/contracts/test_value_outer_set.py::"
                "test_value_outer_set_persisted_payload_rejects_tampered_width"
            ),
        ),
        pytest_case(
            mutation_id="source_flip_proxy_forecast_narrow_set_rejected",
            guard="proxy identification cannot emit a narrow interval",
            replacements=(
                _SourceFlipReplacement(
                    value_outer_set,
                    '        if self.identification_status == "proxy" and not any(\n',
                    '        if False and self.identification_status == "proxy" and not any(\n',
                ),
            ),
            node_id=(
                "tests/unit/core/contracts/test_value_outer_set.py::"
                "test_value_outer_set_proxy_mode_requires_nonzero_interval"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_fixture_world_model_hash_rejected",
            guard="fixture/placeholder world hashes are rejected by corrupt-field drift",
            replacements=(
                _SourceFlipReplacement(
                    validator,
                    "    return bool(\n",
                    "    return False and bool(\n",
                ),
            ),
            probe_command=_python_probe(
                "from tools.quality.validation import check_layer3_gy_value_gate_contract as c\n"
                "try:\n"
                "    c._probe_fixture_world_hash_rejected()\n"
                "except Exception as exc:\n"
                "    print('MUTATION_RED:source_flip_fixture_world_model_hash_rejected:' + str(exc))\n"
                "    raise SystemExit(1)\n"
                "raise SystemExit(0)\n"
            ),
            expected_red_patterns=("MUTATION_RED:source_flip_fixture_world_model_hash_rejected",),
        ),
        pytest_case(
            mutation_id="source_flip_value_world_version_laundered",
            guard="ValueGateReceipt binds value and transport receipts to the WMR hash",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "        if self.transport_receipt.world_model_record_content_hash != (\n",
                    "        if False and self.transport_receipt.world_model_record_content_hash != (\n",
                ),
                _SourceFlipReplacement(
                    generation_cycle,
                    (
                        "        if self.value_outer_set.world_model_record_ref "
                        "!= self.world_model_record_content_hash:\n"
                    ),
                    (
                        "        if False and self.value_outer_set.world_model_record_ref "
                        "!= self.world_model_record_content_hash:\n"
                    ),
                ),
            ),
            node_id=f"{test_value_gate}::test_value_receipt_rejects_world_version_laundering",
        ),
        pytest_case(
            mutation_id="source_flip_dominance_timeout_forced_not_unknown",
            guard="timeout/approximation dominance returns unknown",
            replacements=(
                _SourceFlipReplacement(
                    value_outer_set,
                    '        if force_timeout or timeout_ms == 0:\n            return "unknown"\n',
                    '        if force_timeout or timeout_ms == 0:\n            return "dominates"\n',
                ),
            ),
            node_id=f"{test_value_gate}::test_dominance_timeout_returns_unknown",
        ),
        pytest_case(
            mutation_id="source_flip_simulate_only_shrank_k_world",
            guard="simulate_only receipts may not narrow K_world",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    '        if self.evaluation_mode == "simulate_only" and (\n',
                    '        if False and self.evaluation_mode == "simulate_only" and (\n',
                ),
            ),
            node_id=f"{test_value_gate}::test_simulate_only_receipt_cannot_shrink_k_world",
        ),
        pytest_case(
            mutation_id="source_flip_bad_forecast_minted_value",
            guard="real calibration refusals cannot mint value authority",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "    if any(count > 0 for count in false_clear_counts.values()):\n",
                    "    if False and any(count > 0 for count in false_clear_counts.values()):\n",
                ),
                _SourceFlipReplacement(
                    generation_cycle,
                    '    if support.forecast_tier == "observable_calibrated":\n',
                    '    if False and support.forecast_tier == "observable_calibrated":\n',
                ),
                _SourceFlipReplacement(
                    generation_cycle,
                    '    elif support.forecast_tier != "transported_limited":\n',
                    '    elif False and support.forecast_tier != "transported_limited":\n',
                ),
                _SourceFlipReplacement(
                    generation_cycle,
                    '    if envelope.envelope_status != "pass":\n',
                    '    if False and envelope.envelope_status != "pass":\n',
                ),
            ),
            node_id=f"{test_value_gate}::test_s10_refusal_is_report_driven_by_bad_did_report",
        ),
        pytest_case(
            mutation_id="source_flip_pilot_mode_ran_without_eval_safety",
            guard="pilot/deployment modes block pending EvalSafety",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    '        if mode in {"sandbox_pilot", "field_pilot", "deployment"}:\n',
                    '        if False and mode in {"sandbox_pilot", "field_pilot", "deployment"}:\n',
                ),
            ),
            node_id=f"{test_value_gate}::test_pilot_and_deployment_modes_block_pending_eval_safety",
        ),
        pytest_case(
            mutation_id="source_flip_value_method_selection_fixed_default",
            guard="advisor rank, not a hardcoded method FQN, selects the value method",
            replacements=(
                _SourceFlipReplacement(
                    advisor,
                    ("    selected = runnable_recommended[0]\n    ranked_alternatives = tuple(\n"),
                    (
                        "    selected = next(\n"
                        "        entry\n"
                        "        for entry in catalog.entries\n"
                        '        if entry.fqn == "bayesian.regression.linear_regression@1.0.0"\n'
                        "    )\n"
                        "    ranked_alternatives = tuple(\n"
                    ),
                ),
            ),
            node_id=f"{test_value_gate}::test_candidate_problem_selection_uses_registry_denominator",
        ),
        pytest_case(
            mutation_id="source_flip_value_blocked_candidate_promoted_to_decision_front",
            guard="N6 promotion reducer refuses value_blocked candidates",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "            and not _summary_value_blocks_promotion(summary)\n",
                    "",
                ),
            ),
            node_id=(
                f"{test_generation_cycle}::"
                "test_blocked_value_candidate_cannot_be_promoted_to_decision_front"
            ),
        ),
        pytest_case(
            mutation_id="source_flip_treatment_assignment_owner_required",
            guard="caller-shaped treatment assignment keeps the canonical typed refusal",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    '            code="treatment_assignment_not_owner_derived",\n',
                    '            code="source_flip_caller_assignment_trusted",\n',
                ),
                _SourceFlipReplacement(
                    generation_cycle,
                    (
                        "            acquisition_requirement=value_input_world_knowledge_requirement_gap(\n"
                        '                claim_ref=f"value-claim:{candidate_id}"\n'
                        "            ),\n"
                    ),
                    "            acquisition_requirement=None,\n",
                ),
            ),
            node_id=f"{test_value_gate}::test_shaped_owner_assignment_attestation_is_not_authority",
        ),
        pytest_case(
            mutation_id="source_flip_forged_relation_certificate_rejected",
            guard="a shaped relation certificate cannot alter owner-resolved rows",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "        return profile\n",
                    (
                        '        if _object_get(candidate, "skg_relation_certificate"):\n'
                        "            return profile.model_copy(\n"
                        '                update={"owner_access_ref": "skg://forged-source-flip"}\n'
                        "            )\n"
                        "        return profile\n"
                    ),
                ),
            ),
            node_id=(
                f"{test_value_gate}::"
                "test_shaped_relation_certificate_cannot_open_missing_value_input_lane"
            ),
        ),
        pytest_case(
            mutation_id="source_flip_value_projection_capability_contract_required",
            guard="catalog shape and native output owner must agree on projection capability",
            replacements=(
                _SourceFlipReplacement(
                    advisor,
                    "    if not owner_capabilities:\n        return False\n",
                    "    if False and not owner_capabilities:\n        return False\n",
                ),
                _SourceFlipReplacement(
                    advisor,
                    "    if catalog_capabilities != owner_capabilities:\n        return False\n",
                    "    if False and catalog_capabilities != owner_capabilities:\n        return False\n",
                ),
            ),
            node_id=(
                "tests/unit/foundry/methods/test_selection_advisor.py::"
                "test_value_denominator_rejects_catalog_capability_without_method_owner"
            ),
        ),
        pytest_case(
            mutation_id="source_flip_catalog_replay_rejected",
            guard="selection receipt binds the exact advisor catalog context",
            replacements=(
                _SourceFlipReplacement(
                    advisor,
                    "        if self.selection_context_hash != expected_selection_context_hash:\n",
                    "        if False and self.selection_context_hash != expected_selection_context_hash:\n",
                ),
            ),
            node_id=(
                "tests/unit/foundry/methods/test_selection_advisor.py::"
                "test_value_selection_receipt_rejects_replay_across_catalog_snapshots"
            ),
        ),
        pytest_case(
            mutation_id="source_flip_editable_direct_url_address_rejected",
            guard="editable install addresses cannot become distribution identity",
            replacements=(
                _SourceFlipReplacement(
                    discovery,
                    "                if editable_install is not True:\n",
                    "                if True:\n",
                ),
            ),
            node_id=(
                f"{test_value_gate}::"
                "test_n8_catalog_provenance_accepts_same_editable_source_from_two_paths"
            ),
        ),
        pytest_case(
            mutation_id="source_flip_truthfulness_auto_pass_rejected",
            guard="unverified native uncertainty cannot auto-pass projection",
            replacements=(
                _SourceFlipReplacement(
                    value_evidence,
                    (
                        "        truthfulness is not None\n"
                        "        and truthfulness.effective_truthfulness_tier is TruthfulnessTier.UNVERIFIED\n"
                    ),
                    (
                        "        False and truthfulness is not None\n"
                        "        and truthfulness.effective_truthfulness_tier is TruthfulnessTier.UNVERIFIED\n"
                    ),
                ),
            ),
            node_id=(
                "tests/unit/foundry/methods/test_value_evidence.py::"
                "test_unverified_native_truthfulness_refuses_value_projection"
            ),
        ),
        pytest_case(
            mutation_id="source_flip_estimand_binding_required",
            guard="native intervals bind every authority-bearing estimand field",
            replacements=(
                _SourceFlipReplacement(
                    uncertainty,
                    "        return self == expected\n",
                    "        return self.estimand_id == expected.estimand_id\n",
                ),
            ),
            node_id=(
                "tests/unit/foundry/methods/test_value_evidence.py::"
                "test_same_coefficient_cannot_launder_different_treatment_identity"
            ),
        ),
        pytest_case(
            mutation_id="source_flip_value_input_acquisition_route_required",
            guard="typed value gaps route through the canonical acquisition terminal",
            replacements=(
                _SourceFlipReplacement(
                    generation_cycle,
                    "    if value_port.acquisition_requirement is not None:\n",
                    "    if False and value_port.acquisition_requirement is not None:\n",
                ),
                _SourceFlipReplacement(
                    generation_cycle,
                    '    if value_issue and value_issue.startswith("acquire_data:"):\n',
                    '    if False and value_issue and value_issue.startswith("acquire_data:"):\n',
                ),
            ),
            node_id=(
                f"{test_value_gate}::"
                "test_n8_first_vertical_real_cycle_routes_owner_data_gap_through_n7"
            ),
        ),
        pytest_case(
            mutation_id="source_flip_contract_projection_nonproduction",
            guard="native method projection remains contract-only and nonproduction",
            replacements=(
                _SourceFlipReplacement(
                    value_evidence,
                    "    production_value_eligible: Literal[False] = False\n",
                    "    production_value_eligible: bool = True\n",
                ),
                _SourceFlipReplacement(
                    value_evidence,
                    '        "production_value_eligible": False,\n',
                    '        "production_value_eligible": True,\n',
                ),
            ),
            node_id=(
                "tests/unit/foundry/methods/test_value_evidence.py::"
                "test_verified_native_intervals_remain_projectable"
            ),
        ),
        pytest_case(
            mutation_id="source_flip_world_identity_wmr_ref_binding_required",
            guard="atom WMR refs must resolve to the exact context world",
            replacements=(
                _SourceFlipReplacement(
                    world_model_record,
                    (
                        "    accepted_refs = {\n"
                        "        validated.world_model_record_id,\n"
                        "        validated.content_hash,\n"
                        "    }\n"
                    ),
                    (
                        "    accepted_refs = {\n"
                        "        validated.world_model_record_id,\n"
                        "        validated.content_hash,\n"
                        "        validated_atom.world_model_record_ref,\n"
                        "    }\n"
                    ),
                ),
            ),
            node_id=(
                f"{test_generation_cycle}::"
                "test_joint_port_rejects_candidate_ref_mismatched_to_context_wmr"
            ),
        ),
        pytest_case(
            mutation_id="source_flip_world_identity_problem_frame_binding_required",
            guard="atom problem-frame refs bind the active DesignProblem",
            replacements=(
                _SourceFlipReplacement(
                    cycle_substrate,
                    (
                        "        if (\n"
                        "            design_problem_ref is not None\n"
                        "            and verified_atom.problem_frame_ref != design_problem_ref\n"
                        "        ):\n"
                    ),
                    (
                        "        if (\n"
                        "            False\n"
                        "            and design_problem_ref is not None\n"
                        "            and verified_atom.problem_frame_ref != design_problem_ref\n"
                        "        ):\n"
                    ),
                ),
            ),
            node_id=(
                f"{test_generation_cycle}::"
                "test_cycle_world_identity_rejects_atom_from_another_problem"
            ),
        ),
        pytest_case(
            mutation_id="source_flip_world_identity_target_slot_binding_required",
            guard="every atom target slot resolves through the WMR policy-slot map",
            replacements=(
                _SourceFlipReplacement(
                    world_model_record,
                    (
                        "        binding = validated.slot_binding(slot_id)\n"
                        "        if binding is None or not binding.state_path:\n"
                    ),
                    (
                        "        binding = validated.slot_binding(slot_id)\n"
                        "        if binding is None:\n"
                        "            binding = validated.policy_slot_map[0]\n"
                        "        if not binding.state_path:\n"
                    ),
                ),
            ),
            node_id=(
                "tests/unit/runtime/quality/test_world_model_record.py::"
                "test_world_model_record_resolves_n2_atom_ref_and_binds_target_slots"
            ),
        ),
    )


def _probe_no_value_runtime_hint_reads(repo_root: Path) -> str:
    source = repo_root / "src/polisyos/runtime/quality/generation_cycle.py"
    text = source.read_text(encoding="utf-8")
    pattern = re.compile(
        r'_first_owner_value\(hints|runtime_hints\.get\("'
        r"(world_model_record|method_state|panel_observational_data|"
        r"outcome_prediction|forecast_support|value_)"
    )
    matches = [
        f"{line_no}:{line.strip()}"
        for line_no, line in enumerate(text.splitlines(), start=1)
        if pattern.search(line)
    ]
    if matches:
        raise AssertionError("value input read from runtime_hints: " + "; ".join(matches))
    return "Production N8 path has zero value-input runtime_hints reads."


def _probe_empty_hints_owner_access() -> str:
    from polisyos.runtime.quality.generation_cycle import FoundryValuePort, RealValueOwnerGateway

    problem = _audit_problem()
    if problem.runtime_hints:
        raise AssertionError("audit problem unexpectedly contains value hints")
    observation = _quiet_call(
        lambda: FoundryValuePort(
            owner_gateway=RealValueOwnerGateway(repo_root=_repo_root()),
            requested_method_fqn="causal.inference.synthetic_control@1.0.0",
        )(
            candidate=_AuditCandidate(
                "candidate_no_hints_gap",
                _AuditAtom("candidate_no_hints_gap", _hash("4")),
                ("grant", "firms", "panel", "no_hints"),
            ),
            simulation=_audit_simulation(),
            problem=problem,
            cycle_index=0,
        )
    )
    blockers = tuple(observation.authority_blockers)
    if blockers != ("acquire_data:value_panel_data_missing",):
        raise AssertionError(f"expected real panel-data acquisition gap, got {blockers}")
    reason = str(observation.reason)
    if (
        "substrate owner" not in reason
        or "dataset_catalog.duckdb#variable/firm_survival" not in reason
    ):
        raise AssertionError(f"block did not show real substrate owner access: {reason}")
    return "Empty runtime_hints reached real substrate owner and blocked on L1 DCAT gap."


def _probe_audit_not_fed_by_hints() -> str:
    problem = _audit_problem()
    if problem.runtime_hints:
        raise AssertionError(f"audit problem carries value hints: {problem.runtime_hints}")
    observation = _run_real_owner_value_refusal()
    if observation.status != "value_blocked" or observation.value_receipt is not None:
        raise AssertionError(f"expected honest value refusal, got {observation.status}")
    if observation.authority_blockers != ("treatment_assignment_not_owner_derived",):
        raise AssertionError(
            f"unexpected owner-assignment blockers: {observation.authority_blockers}"
        )
    if observation.method_selection_receipt is None:
        raise AssertionError("real advisor receipt missing before treatment refusal")
    if observation.acquisition_requirement is None:
        raise AssertionError("canonical N7 acquisition route missing")
    return (
        "Audit lane uses real owner rows and advisor selection, then refuses missing "
        "owner treatment assignment and routes the canonical N7 requirement."
    )


def _probe_missing_wmr_is_wiring_error() -> str:
    from polisyos.runtime.quality.generation_cycle import (
        FoundryValuePort,
        RealValueOwnerGateway,
        SimulationPortObservation,
    )

    observation = _quiet_call(
        lambda: FoundryValuePort(
            owner_gateway=RealValueOwnerGateway(repo_root=_repo_root()),
            requested_method_fqn="causal.inference.synthetic_control@1.0.0",
        )(
            candidate=_AuditCandidate(
                "candidate_missing_wmr",
                _AuditAtom("candidate_missing_wmr", _hash("5")),
                ("grant", "firms", "panel", "missing_wmr"),
            ),
            simulation=SimulationPortObservation(
                candidate_id="candidate_missing_wmr",
                status="joint_simulated",
                simulation_ref=_hash("7"),
            ),
            problem=_audit_problem(),
            cycle_index=0,
        )
    )
    blockers = tuple(observation.authority_blockers)
    if blockers != ("value_world_model_record_unwired",):
        raise AssertionError(f"missing WMR was not a wiring error: {blockers}")
    return "Missing cycle WMR fails as controller wiring, not acquire_data."


def _probe_fixture_world_hash_rejected() -> str:
    if not _is_fixture_world_hash(_hash("1")):
        raise AssertionError("placeholder fixture hash was not recognized")
    world_hash = _audit_world_record().content_hash
    if _is_fixture_world_hash(world_hash):
        raise AssertionError("real audit WMR hash looked like a fixture placeholder")
    return f"Placeholder WMR hash rejected; audit WMR is {world_hash}."


def _probe_supplied_width_rejected() -> str:
    value_set = _value_set("point", lower=(1.0,), upper=(1.0,))
    payload = value_set.model_dump(mode="json")
    try:
        ValueOuterSet.model_validate(payload)
    except ValueError as exc:
        if "value_outer_set_width_supplied_not_derived" in str(exc):
            return "ValueOuterSet.model_validate rejects non-empty supplied width."
    raise AssertionError("supplied width accepted")


def _probe_persisted_width_tamper_rejected() -> str:
    value_set = _value_set("partial", lower=(1.0,), upper=(2.0,))
    payload = value_set.model_dump(mode="json")
    payload["width"] = [0.5]
    try:
        ValueOuterSet.from_persisted_payload(payload)
    except ValueError as exc:
        if "value_outer_set_width_tampered" in str(exc):
            return "Persisted ValueOuterSet rejects a tampered derived-width checksum."
    raise AssertionError("tampered persisted width accepted")


def _probe_proxy_narrow_rejected() -> str:
    try:
        _value_set("proxy", lower=(1.0,), upper=(1.0,), forecast_tier="transported_limited")
    except ValueError as exc:
        if "bounded_identification_requires_nonzero_interval" in str(exc):
            return "Proxy identification cannot emit a narrow/point set."
    raise AssertionError("proxy narrow set accepted")


def _probe_world_laundering_rejected() -> str:
    receipt = _receipt_object("point")
    payload = receipt.model_dump(mode="python")
    payload["value_outer_set"] = receipt.value_outer_set
    payload["transport_receipt"] = receipt.transport_receipt
    payload["calibration_receipt"] = receipt.calibration_receipt
    payload["world_model_record_content_hash"] = _hash("2")
    try:
        ValueGateReceipt.model_validate(payload)
    except ValueError as exc:
        if "value_world_version_laundered" in str(exc):
            return "Receipt refuses V1 value as authority for V2 world hash."
    raise AssertionError("world-version laundering accepted")


def _probe_timeout_unknown() -> str:
    left = _value_set("partial", lower=(3.0,), upper=(4.0,))
    right = _value_set("partial", lower=(1.0,), upper=(2.0,))
    if left.compare(right) != "dominates":
        raise AssertionError("fixture does not dominate without timeout")
    if left.compare(right, force_timeout=True) != "unknown":
        raise AssertionError("timeout did not return unknown")
    return "Timeout/approximation path returns unknown, not dominance."


def _probe_simulate_only_shrink_rejected() -> str:
    receipt = _receipt_object("point")
    payload = receipt.model_dump(mode="python")
    payload["value_outer_set"] = receipt.value_outer_set
    payload["transport_receipt"] = receipt.transport_receipt
    payload["calibration_receipt"] = receipt.calibration_receipt
    payload["k_world_ref_after"] = _hash("3")
    try:
        ValueGateReceipt.model_validate(payload)
    except ValueError as exc:
        if "simulate_only_shrank_k_world" in str(exc):
            return "simulate_only receipt refuses K_world narrowing."
    raise AssertionError("simulate_only K_world shrink accepted")


def _probe_bad_forecast_cases_blocked() -> str:
    from polisyos.runtime.quality.generation_cycle import (
        FoundryValuePort,
        RealValueOwnerGateway,
        _run_value_transport,
    )

    cases = {
        "uncalibrated": {
            "owner": _AdversarialAuditGateway(
                forecast_tier="simulation_only_advisory",
                calibration_status=None,
            ),
            "method": "causal.inference.did.standard@1.0.0",
        },
        "unsupported": {
            "owner": RealValueOwnerGateway(repo_root=_repo_root()),
            "method": "causal.inference.no_such_method@9.9.9",
        },
        "regime_laundered": {
            "owner": _AdversarialAuditGateway(
                expected_policy_context_ref="policy-context://other-regime"
            ),
            "method": "causal.inference.did.standard@1.0.0",
        },
    }
    observed = []
    for name, config in cases.items():
        observation = _quiet_call(
            lambda name=name, config=config: FoundryValuePort(
                owner_gateway=config["owner"],
                requested_method_fqn=str(config["method"]),
            )(
                candidate=_AuditCandidate(
                    "candidate_bad_forecast",
                    _AuditAtom(
                        "candidate_bad_forecast",
                        _hash("4"),
                        target_world_slots=("avg_income",),
                        treated_unit_ids=("AM",),
                        treatment_period=2020,
                    ),
                    ("grant", "firms", "value", name),
                ),
                simulation=_audit_simulation(),
                problem=_audit_problem(),
                cycle_index=0,
            )
        )
        if observation.status != "value_blocked" or observation.value_receipt is not None:
            raise AssertionError(f"{name} minted value")
        observed.append(f"{name}:{observation.authority_blockers[0]}")
    transport, error = _run_value_transport(
        inputs={
            "selection_diagram": {"invalid": "selection-diagram"},
            "query_treatment": "candidate_bad_forecast",
            "query_outcome": "avg_income",
        },
        world_record=_audit_world_record(),
    )
    if transport is not None or not str(error or "").startswith("untransportable_forecast"):
        raise AssertionError("untransportable forecast minted value")
    observed.append(f"untransportable:{error}")
    return "; ".join(observed)


def _probe_mode_gates_block() -> str:
    from polisyos.runtime.quality.generation_cycle import FoundryValuePort, RealValueOwnerGateway

    blocked = []
    for mode in ("sandbox_pilot", "field_pilot", "deployment"):
        observation = FoundryValuePort(
            owner_gateway=RealValueOwnerGateway(repo_root=_repo_root()),
            evaluation_mode=mode,
            requested_method_fqn="causal.inference.synthetic_control@1.0.0",
        )(
            candidate=_AuditCandidate(
                "candidate_mode_gate",
                _AuditAtom("candidate_mode_gate", _hash("5")),
                ("grant", "firms", "mode", mode),
            ),
            simulation=_audit_simulation(),
            problem=_audit_problem(),
            cycle_index=0,
        )
        if observation.authority_blockers != ("eval_safety_gate_unavailable",):
            raise AssertionError(f"{mode} did not block on EvalSafety")
        blocked.append(mode)
    return "EvalSafety blocks " + ",".join(blocked)


def _probe_selection_not_fixed_default() -> str:
    from polisyos.foundry.methods.selection import select_value_method_for_problem

    selection = _quiet_call(
        lambda: select_value_method_for_problem(
            candidate={
                "candidate_id": "candidate_panel",
                "atom": {"target_world_slots": ("panel", "firm_survival")},
            },
            problem={
                "design_problem_id": "selector_problem",
                "runtime_hints": {
                    "value_method_hint": "panel",
                    "value_required_data_modalities": ("panel",),
                },
            },
        )
    )
    if selection.get("selection_source") != "foundry_registry_advisor":
        raise AssertionError("selector did not use Foundry advisor")
    denominator = tuple(selection.get("denominator") or ())
    if len(denominator) <= 1:
        raise AssertionError("selector denominator collapsed to a fixed default")
    if not selection.get("score_trace"):
        raise AssertionError("selector did not expose advisor scoring trace")
    for path in (
        "src/polisyos/runtime/quality/workspace/loop.py",
        "src/polisyos/foundry/methods/compiler/plan_optimizer.py",
    ):
        text = (_repo_root() / path).read_text(encoding="utf-8")
        if "causal.inference.synthetic_control@1.0.0" in text:
            raise AssertionError(f"fixed synthetic_control default survives in {path}")
    return (
        f"Advisor selected {selection.get('selected_method_fqn')} after scoring "
        f"{len(denominator)} reachable value methods; fixed-default source grep is clean."
    )


def _probe_value_blocks_promotion() -> str:
    from polisyos.runtime.quality.generation_cycle import (
        CandidateSummary,
        PromotionPortObservation,
        _apply_promotion_to_summaries,
    )

    summary = CandidateSummary(
        candidate_id="candidate_value_blocked",
        content_hash=_hash("6"),
        cycle_index=0,
        generation_channel="n4_owner",
        proxy_score=0.2,
        voi_estimate=0.1,
        grounding_status="current_valid",
        grounding_source="cgf_firewall",
        grounding_disposition="shadow_bound",
        grounding_score=0.9,
        current_valid=True,
        value_status="value_blocked",
        value_decision_grade="blocked",
        value_blockers=("uncalibrated_forecast_minted_value",),
        front="research",
        high_proxy=False,
        low_grounding=False,
    )
    promoted = _apply_promotion_to_summaries(
        (summary,),
        PromotionPortObservation(
            status="certified_current_valid",
            certified_candidate_ids=("candidate_value_blocked",),
        ),
    )
    if promoted[0].front == "decision":
        raise AssertionError("blocked value promoted to DecisionFront")
    return "N6 promotion reducer refuses value_blocked summary."


def _receipt_object(identification_status: str) -> ValueGateReceipt:
    payload = _receipt_payload(
        identification_status,
        lower=(6.0,) if identification_status == "point" else (2.0,),
        upper=(6.0,) if identification_status == "point" else (5.0,),
        transport_status="identified",
    )
    payload.pop("value_outer_set_width_derived", None)
    payload["value_outer_set"] = ValueOuterSet.from_persisted_payload(payload["value_outer_set"])
    return ValueGateReceipt.model_validate(payload)


def _audit_simulation() -> Any:
    from polisyos.runtime.quality.generation_cycle import SimulationPortObservation

    world = _audit_world_record()
    return SimulationPortObservation(
        candidate_id="candidate_audit",
        status="joint_simulated",
        simulation_ref=_hash("7"),
        k_world_ref_before=world.content_hash,
        k_world_ref_after=world.content_hash,
        world_model_record=world,
    )


def _audit_value_candidate(candidate_id: str = "candidate_live_value") -> _AuditCandidate:
    return _AuditCandidate(
        candidate_id,
        _AuditAtom(
            candidate_id,
            _hash("8"),
            target_world_slots=("avg_income",),
        ),
        ("grant", "country", "avg_income", "real_panel"),
    )


@dataclass(frozen=True)
class _AdversarialAuditGateway:
    forecast_tier: str = "observable_calibrated"
    calibration_status: str | None = "pass"
    expected_policy_context_ref: str | None = None
    selection_diagram: object | None = None

    def load_panel_observational_data(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: Any,
    ) -> object:
        from polisyos.runtime.quality.generation_cycle import RealValueOwnerGateway

        return RealValueOwnerGateway(repo_root=_repo_root()).load_panel_observational_data(
            candidate=candidate,
            problem=problem,  # type: ignore[arg-type]
            world_record=world_record,
        )

    def produce_forecast_inputs(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: Any,
        method_result: object,
        selected_method_fqn: str,
    ) -> Mapping[str, Any]:
        from polisyos.runtime.quality.generation_cycle import (
            _build_s10_forecast_inputs,
            _s10_calibration_evidence_from_report,
        )

        policy_context_ref = f"policy-context://{world_record.world_model_record_id}"
        evidence = _s10_calibration_evidence_from_report(method_result.output.get("report"))
        if self.calibration_status not in {None, "pass"}:
            evidence = {
                **evidence,
                "calibration_status": self.calibration_status,
                "numerator": 0,
                "pass_rate": 0.0,
                "floor_passed": False,
            }
        return _build_s10_forecast_inputs(
            candidate=candidate,
            problem=problem,  # type: ignore[arg-type]
            world_record=world_record,
            method_result=method_result,
            selected_method_fqn=selected_method_fqn,
            forecast_tier=self.forecast_tier,
            calibration_status=self.calibration_status,
            policy_context_ref=policy_context_ref,
            expected_policy_context_ref=self.expected_policy_context_ref or policy_context_ref,
            false_clear_counts=evidence["false_clear_counts"],  # type: ignore[arg-type]
            calibration_evidence=evidence,
        )

    def build_transport_inputs(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: Any,
    ) -> Mapping[str, Any]:
        from polisyos.runtime.quality.generation_cycle import (
            ValueOwnerAccessError,
            _candidate_transport_outcome_variable,
            _candidate_transport_treatment_variable,
        )

        del world_record
        if self.selection_diagram is None:
            raise ValueOwnerAccessError(
                "acquire_data:transport_context_unresolved",
                "adversarial audit gateway has no content-bound transport context",
                owner_access_ref="audit_gateway://transport_context_missing",
            )
        query_treatment = _candidate_transport_treatment_variable(candidate)
        query_outcome = _candidate_transport_outcome_variable(candidate, problem)  # type: ignore[arg-type]
        return {
            "selection_diagram": self.selection_diagram,
            "query_treatment": query_treatment,
            "query_outcome": query_outcome,
        }


@cache
def _run_real_owner_value_refusal() -> Any:
    from polisyos.runtime.quality.generation_cycle import FoundryValuePort

    lane = _canonical_first_vertical_lane()
    return _quiet_call(
        lambda: FoundryValuePort(
            repo_root=_repo_root(),
            cycle_substrate_context=lane["cycle_substrate_context"],
        )(
            candidate=lane["candidate"],
            simulation=lane["simulation"],
            problem=lane["problem"],
            cycle_index=0,
        )
    )


def _audit_problem() -> DesignProblem:
    """Build the N8 audit problem through the canonical typed front door."""

    return DesignProblem(
        design_problem_id="value_gate_audit_problem",
        problem_statement="Audit N8 value gate.",
        domain="runtime_quality",
        nl_provenance=NLProvenance(
            raw_request="Estimate the effect of the bound audit intervention on average income.",
            source_surface="gy_n8_value_gate_contract",
        ),
        authority_profile=AuthorityProfile(
            requester_authority="quality_audit",
            requested_authority_level="research",
            mandate="Recompute the non-promotable N8 value-gate receipt.",
        ),
        jurisdiction_time=JurisdictionTimeSemantics(
            region="UA",
            valid_time="2018/2023",
            as_of="2026-07-06T00:00:00+00:00",
            policy_time="2020",
            data_time="2018/2023",
        ),
        objectives=[
            DesignObjective(
                objective_id="increase_average_income",
                description="Estimate whether the intervention increases average income.",
                metric_id="avg_income",
            )
        ],
        stakeholders=[
            DesignStakeholder(
                stakeholder_id="households",
                name="Households",
                role="affected_population",
            )
        ],
        outcome_of_interest=OutcomeOfInterest(
            target_variable="avg_income",
            metric_id="avg_income",
            estimand="average_treatment_effect",
        ),
        candidate_lever_space=CandidateLeverSpace(
            allowed_operator_kinds=["income_support"],
            candidate_levers=[
                CandidateLever(
                    lever_id="income_support",
                    operator_kind="income_support",
                    instrument="audit.income_support",
                    target_slot="avg_income",
                )
            ],
        ),
        evidence_acquisition_needs=EvidenceAcquisitionNeeds(),
        runtime_hints={},
    )


def _authority_boundary() -> dict[str, Any]:
    return {
        "authoritative_for": ["forecast_support_tiering", "observable_subset_calibration"],
        "may_not_use_for": [
            "production_recommendation",
            "production_claim_authority",
            "rollout_authority",
            "publication_authority",
            "claim_authority",
            "closeout_authority",
        ],
        "source_authority": "deterministic_producer",
        "posture": "shadow",
        "rule_version_refs": ["policyos.layer2.s10.outcome_prediction.v1"],
    }


def _governed_denominators_projection(value: object) -> object:
    """Project only the catalog provenance nested inside an N8 denominator set."""

    from polisyos.foundry.methods.catalog.snapshot import (
        method_catalog_governed_provenance_projection,
    )

    if not isinstance(value, Mapping):
        return deepcopy(value)
    projection = deepcopy(dict(value))
    catalog_provenance = value.get("catalog_provenance")
    if isinstance(catalog_provenance, Mapping):
        projection["catalog_provenance"] = method_catalog_governed_provenance_projection(
            catalog_provenance
        )
    return projection


def _governed_value_gate_projection(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return the complete N8 comparison payload with ambient custody non-decisive."""

    projection = deepcopy(dict(payload))
    projection.pop("contract_content_hash", None)
    if "denominators" in projection:
        projection["denominators"] = _governed_denominators_projection(projection["denominators"])
    return projection


def run_rederive_audit_result(
    repo_root: Path,
    *,
    expected_source_freeze: str | None = None,
) -> ValueGateValidationResult:
    """Recompute N8 while retaining ambient diagnostics in the audit result."""

    _ensure_src_path(repo_root)
    if expected_source_freeze is None:
        return ValueGateValidationResult(
            governing_issues=({"code": "catalog_dependency_source_freeze_not_supplied"},),
            ambient_findings=(),
        )
    started = time.monotonic()
    expected = build_payload(
        repo_root,
        expected_source_freeze=expected_source_freeze,
    )
    expected_result = validate_payload_result(
        expected,
        expected_source_freeze=expected_source_freeze,
    )
    issues = list(expected_result.governing_issues)
    ambient_findings = list(expected_result.ambient_findings)
    path = repo_root / OUTPUT_PATH
    if not path.exists():
        issues.append({"code": "artifact_missing", "path": OUTPUT_PATH})
    else:
        actual = _load_json(path)
        actual_result = validate_payload_result(
            actual,
            expected_source_freeze=expected_source_freeze,
        )
        issues.extend(actual_result.governing_issues)
        ambient_findings.extend(actual_result.ambient_findings)
        if actual != expected:
            issues.append(
                {
                    "code": "live_rederive_section_drift",
                    "section": "catalog_dependency_authority",
                }
            )
    authority = expected["catalog_dependency_authority"]
    if authority["result_kind"] == "runtime_cutoff_not_established":
        authority_failure = authority["preflight_refusal"]["failure"]
    else:
        authority_failure = authority["failure"]
    print(
        json.dumps(
            {
                "status": "pass" if not issues else "fail",
                "wall_time_ms": round((time.monotonic() - started) * 1000.0, 3),
                "catalog_dependency_result_kind": authority["result_kind"],
                "catalog_dependency_failure_code": authority_failure["failure_code"],
                "ambient_findings": list(_deduplicate_findings(ambient_findings)),
            },
            sort_keys=True,
        )
    )
    return ValueGateValidationResult(
        governing_issues=_deduplicate_findings(issues),
        ambient_findings=_deduplicate_findings(ambient_findings),
    )


def run_rederive_audit(
    repo_root: Path,
    *,
    expected_source_freeze: str | None = None,
) -> tuple[dict[str, Any], ...]:
    """Return governing rederive failures for backward-compatible consumers."""

    return run_rederive_audit_result(
        repo_root,
        expected_source_freeze=expected_source_freeze,
    ).governing_issues


def _content_hash(payload: Mapping[str, Any]) -> str:
    filtered = {
        key: value for key, value in payload.items() if key not in CONTENT_HASH_EXCLUDED_TOP_LEVEL
    }
    encoded = json.dumps(filtered, sort_keys=True, separators=(",", ":")).encode("utf-8")
    import hashlib

    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _is_fixture_world_hash(value: object) -> bool:
    text = str(value or "")
    return bool(
        text.startswith("sha256:")
        and len(text) == len("sha256:") + 64
        and len(set(text.removeprefix("sha256:"))) == 1
    )


def _deduplicate_findings(
    findings: list[dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    seen: set[str] = set()
    deduplicated: list[dict[str, Any]] = []
    for finding in findings:
        identity = json.dumps(finding, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        if identity not in seen:
            seen.add(identity)
            deduplicated.append(finding)
    return tuple(deduplicated)


def _is_valid_catalog_ambient_admission(value: object) -> bool:
    return bool(
        isinstance(value, Mapping)
        and set(value) == {"status", "included_in_governed_denominator", "fail_closed_action"}
        and value.get("included_in_governed_denominator") is False
        and value.get("fail_closed_action") == "quarantine"
        and value.get("status") in {"quarantined_unbound", "declared_not_admitted"}
    )


def _is_structurally_non_decisive_predicate(value: object) -> bool:
    return bool(
        isinstance(value, Mapping)
        and value.get("decisive") is False
        and value.get("fail_closed_action") == "quarantine"
    )


def _catalog_provenance_validation_result(
    recorded: object,
    expected: Mapping[str, Any],
    *,
    denominator_fields: frozenset[str] | None = None,
) -> ValueGateValidationResult:
    from polisyos.foundry.methods.catalog.snapshot import (
        MethodCatalogDiscoveryProvenanceError,
        method_catalog_governed_provenance_id,
        method_catalog_provenance_id,
    )

    governing: list[dict[str, Any]] = []
    ambient_findings: list[dict[str, Any]] = []
    if not isinstance(recorded, Mapping):
        return ValueGateValidationResult(
            governing_issues=({"code": "catalog_discovery_provenance_missing"},),
            ambient_findings=(),
        )

    recorded_provenance_id = recorded.get("provenance_id")
    try:
        recomputed_provenance_id = method_catalog_provenance_id(recorded)
    except (TypeError, ValueError):
        recomputed_provenance_id = None
    if (
        not isinstance(recorded_provenance_id, str)
        or recorded_provenance_id != recomputed_provenance_id
    ):
        governing.append({"code": "catalog_provenance_content_hash_mismatch"})

    recorded_projection_id: str | None = None
    expected_projection_id: str | None = None
    try:
        recorded_projection_id = method_catalog_governed_provenance_id(recorded)
    except MethodCatalogDiscoveryProvenanceError as exc:
        governing.append({"code": str(exc)})
    try:
        expected_projection_id = method_catalog_governed_provenance_id(expected)
    except MethodCatalogDiscoveryProvenanceError as exc:
        governing.append({"code": str(exc)})

    recorded_governed = recorded.get("governed_discovery")
    expected_governed = expected.get("governed_discovery")
    if not isinstance(recorded_governed, Mapping) or not isinstance(expected_governed, Mapping):
        governing.append({"code": "catalog_governed_discovery_manifest_missing"})
    else:
        if recorded_governed.get("source_policy") != expected_governed.get("source_policy"):
            governing.append({"code": "catalog_governed_source_policy_mismatch"})
        if any(
            recorded_governed.get(field) != expected_governed.get(field)
            for field in (
                "manifest_id",
                "component_count",
                "component_set_sha256",
                "registry_fqn_set_sha256",
                "registry_binding_sha256",
                "unbound_inputs",
            )
        ):
            governing.append({"code": "catalog_builtin_discovery_manifest_mismatch"})
        if recorded_governed.get("unbound_inputs"):
            governing.append({"code": "catalog_governed_discovery_manifest_unbound"})

    recorded_ambient = recorded.get("ambient_discovery")
    expected_ambient = expected.get("ambient_discovery")
    ambient_admission_valid = False
    if not isinstance(recorded_ambient, Mapping) or not isinstance(expected_ambient, Mapping):
        governing.append({"code": "catalog_ambient_discovery_manifest_missing"})
    else:
        recorded_admission = recorded_ambient.get("admission")
        expected_admission = expected_ambient.get("admission")
        ambient_admission_valid = _is_valid_catalog_ambient_admission(
            recorded_admission
        ) and _is_valid_catalog_ambient_admission(expected_admission)
        ambient_destination = ambient_findings if ambient_admission_valid else governing
        if recorded_ambient.get("source_policy") != expected_ambient.get("source_policy"):
            governing.append({"code": "catalog_ambient_source_policy_mismatch"})
        if recorded_ambient.get("manifest_id") != expected_ambient.get("manifest_id"):
            ambient_destination.append({"code": "catalog_ambient_discovery_manifest_mismatch"})
        if recorded_ambient.get("entry_points") != expected_ambient.get("entry_points"):
            ambient_destination.append(
                {"code": "catalog_entry_point_distribution_manifest_mismatch"}
            )
        if any(
            recorded_ambient.get(field) != expected_ambient.get(field)
            for field in ("dev_scan_roots", "dev_scan_files")
        ):
            ambient_destination.append({"code": "catalog_development_scan_manifest_mismatch"})
        if any(
            recorded_ambient.get(field) != expected_ambient.get(field)
            for field in (
                "component_count",
                "component_set_sha256",
                "added_component_ids",
                "overlap_component_count",
                "overlap_component_set_sha256",
            )
        ):
            ambient_destination.append({"code": "catalog_ambient_component_manifest_mismatch"})
        if recorded_ambient.get("unbound_inputs") != expected_ambient.get("unbound_inputs"):
            ambient_destination.append({"code": "catalog_ambient_unbound_input_manifest_mismatch"})
        if recorded_admission != expected_admission:
            ambient_destination.append({"code": "catalog_ambient_admission_mismatch"})
        if not _is_valid_catalog_ambient_admission(recorded_admission):
            governing.append({"code": "catalog_ambient_input_not_quarantined"})

    recorded_runtime = recorded.get("runtime_backend_identity")
    expected_runtime = expected.get("runtime_backend_identity")
    if not isinstance(recorded_runtime, Mapping) or not isinstance(expected_runtime, Mapping):
        governing.append({"code": "catalog_runtime_backend_identity_missing"})
    else:
        if recorded_runtime.get("schema_version") != expected_runtime.get("schema_version"):
            governing.append({"code": "catalog_runtime_backend_identity_mismatch"})
        if recorded_runtime.get("identity_id") != expected_runtime.get("identity_id"):
            governing.append({"code": "catalog_runtime_backend_identity_mismatch"})
        if recorded_runtime.get("runtime_packages") != expected_runtime.get("runtime_packages"):
            governing.append({"code": "catalog_runtime_package_identity_mismatch"})
        if any(
            recorded_runtime.get(field) != expected_runtime.get(field)
            for field in (
                "backend_fingerprints",
                "entry_runtime_binding_count",
                "entry_runtime_bindings_sha256",
            )
        ):
            governing.append({"code": "catalog_backend_fingerprint_mismatch"})

    predicate_rows = recorded.get("predicate_provenance")
    expected_predicate_rows = expected.get("predicate_provenance")
    recorded_by_predicate: dict[str, Mapping[str, Any]] = {}
    expected_by_predicate: dict[str, Mapping[str, Any]] = {}
    if not isinstance(predicate_rows, list) or not isinstance(expected_predicate_rows, list):
        governing.append({"code": "catalog_predicate_provenance_missing"})
    else:
        for rows, destination in (
            (predicate_rows, recorded_by_predicate),
            (expected_predicate_rows, expected_by_predicate),
        ):
            for row in rows:
                if not isinstance(row, Mapping) or not isinstance(row.get("predicate"), str):
                    governing.append({"code": "catalog_predicate_provenance_invalid"})
                    continue
                predicate = str(row["predicate"])
                if not predicate or predicate in destination:
                    governing.append({"code": "catalog_predicate_provenance_invalid"})
                    continue
                destination[predicate] = row
                classification = str(row.get("classification") or "")
                if (
                    classification
                    in {
                        "consumer_asserted",
                        "institutionally_supplied",
                        "not_established",
                    }
                    and row.get("decisive") is True
                ):
                    governing.append(
                        {
                            "code": "catalog_predicate_provenance_not_admissible",
                            "predicate": predicate,
                            "classification": classification,
                        }
                    )
        for predicate in sorted(set(recorded_by_predicate) | set(expected_by_predicate)):
            recorded_row = recorded_by_predicate.get(predicate)
            expected_row = expected_by_predicate.get(predicate)
            if recorded_row == expected_row:
                continue
            finding = {
                "code": "catalog_predicate_provenance_mismatch",
                "predicate": predicate,
            }
            if (
                ambient_admission_valid
                and _is_structurally_non_decisive_predicate(recorded_row)
                and _is_structurally_non_decisive_predicate(expected_row)
            ):
                ambient_findings.append(finding)
            else:
                governing.append(finding)
        recorded_order = [
            str(row.get("predicate")) for row in predicate_rows if isinstance(row, Mapping)
        ]
        expected_order = [
            str(row.get("predicate")) for row in expected_predicate_rows if isinstance(row, Mapping)
        ]
        if set(recorded_order) == set(expected_order) and recorded_order != expected_order:
            governing.append({"code": "catalog_predicate_provenance_order_mismatch"})

    predicate_bindings = recorded.get("predicate_bindings")
    expected_predicate_bindings = expected.get("predicate_bindings")
    if predicate_bindings != expected_predicate_bindings:
        governing.append({"code": "catalog_predicate_bindings_mismatch"})
    if denominator_fields is not None:
        if not isinstance(predicate_bindings, Mapping) or set(predicate_bindings) != set(
            denominator_fields
        ):
            governing.append({"code": "catalog_predicate_binding_coverage_mismatch"})
        else:
            known_predicates = set(recorded_by_predicate)
            for field, references in predicate_bindings.items():
                if (
                    not isinstance(references, list)
                    or not references
                    or any(
                        not isinstance(reference, str) or reference not in known_predicates
                        for reference in references
                    )
                ):
                    governing.append(
                        {
                            "code": "catalog_predicate_binding_invalid",
                            "field": field,
                        }
                    )

    admission_policy = recorded.get("predicate_admission_policy")
    expected_admission_policy = expected.get("predicate_admission_policy")
    if admission_policy != expected_admission_policy:
        governing.append({"code": "catalog_predicate_admission_policy_mismatch"})
    if recorded.get("schema_version") != expected.get("schema_version"):
        governing.append({"code": "catalog_provenance_schema_version_mismatch"})
    if (
        recorded_projection_id is not None
        and expected_projection_id is not None
        and recorded_projection_id != expected_projection_id
        and not governing
    ):
        governing.append({"code": "catalog_governed_provenance_manifest_mismatch"})
    return ValueGateValidationResult(
        governing_issues=_deduplicate_findings(governing),
        ambient_findings=_deduplicate_findings(ambient_findings),
    )


def _catalog_provenance_issues(
    recorded: object,
    expected: Mapping[str, Any],
    *,
    denominator_fields: frozenset[str] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Return only governing catalog-provenance failures for legacy consumers."""

    return _catalog_provenance_validation_result(
        recorded,
        expected,
        denominator_fields=denominator_fields,
    ).governing_issues


def validate_payload_result(
    payload: Mapping[str, Any],
    *,
    expected_source_freeze: str | None = None,
) -> ValueGateValidationResult:
    """Validate N8 and retain non-decisive ambient findings separately."""

    issues: list[dict[str, Any]] = []
    ambient_findings: list[dict[str, Any]] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append({"code": "schema_version_mismatch"})
    if payload.get("rule_version") != VALUE_GATE_RULE_VERSION:
        issues.append({"code": "rule_version_mismatch"})
    authority_payload = payload.get("catalog_dependency_authority")
    if isinstance(authority_payload, Mapping):
        from pydantic import TypeAdapter

        from polisyos.foundry.methods.catalog.dependency_authority import (
            MethodCatalogDependencyAuthorityResult,
            SourceRejectedMethodCatalogDependencyProfile,
            SourceUnestablishedMethodCatalogDependencyProfile,
            UnestablishedMethodCatalogDependencyProfile,
        )

        try:
            authority_result = TypeAdapter(MethodCatalogDependencyAuthorityResult).validate_json(
                json.dumps(
                    authority_payload,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                strict=True,
            )
        except ValidationError:
            issues.append({"code": "catalog_dependency_authority_invalid"})
        else:
            if isinstance(
                authority_result,
                UnestablishedMethodCatalogDependencyProfile,
            ):
                refusal = authority_result.preflight_refusal
                if (
                    refusal.failure.failure_code.value
                    != "owner_enforced_runtime_subtree_cutoff_not_established"
                    or refusal.persistence.status != "not_established"
                    or refusal.persistence.missing_capability
                    != "owner_resolved_resolution_receipt_store"
                ):
                    issues.append({"code": "catalog_dependency_authority_refusal_drift"})
                recorded_freeze = refusal.request.pre_source_request.expected_source_freeze_commit
            elif isinstance(
                authority_result,
                (
                    SourceRejectedMethodCatalogDependencyProfile,
                    SourceUnestablishedMethodCatalogDependencyProfile,
                ),
            ):
                if (
                    authority_result.persistence.status != "not_established"
                    or authority_result.persistence.missing_capability
                    != "owner_resolved_resolution_receipt_store"
                ):
                    issues.append({"code": "catalog_dependency_authority_refusal_drift"})
                if isinstance(
                    authority_result,
                    SourceRejectedMethodCatalogDependencyProfile,
                ):
                    recorded_freeze = (
                        authority_result.request.pre_source_request.expected_source_freeze_commit
                    )
                else:
                    recorded_freeze = authority_result.request.expected_source_freeze_commit
            else:  # pragma: no cover - closed union guarded by the TypeAdapter
                issues.append({"code": "catalog_dependency_authority_variant_unknown"})
                recorded_freeze = None
            if recorded_freeze is not None:
                if expected_source_freeze is None:
                    issues.append({"code": "catalog_dependency_source_freeze_not_supplied"})
                elif recorded_freeze != expected_source_freeze:
                    issues.append({"code": "catalog_dependency_source_freeze_mismatch"})
        if payload.get("status") != "not_established":
            issues.append({"code": "catalog_dependency_status_promoted"})
        if payload.get("retained_capability_label") != "producer_missing":
            issues.append({"code": "catalog_dependency_capability_label_promoted"})
        allowed = {
            "schema_version",
            "rule_version",
            "gy_lifecycle_marker",
            "produced_by",
            "status",
            "catalog_dependency_authority",
            "retained_capability_label",
            "contract_content_hash",
        }
        if set(payload) != allowed:
            issues.append({"code": "catalog_dependency_nonreceipt_shape_drift"})
        if payload.get("contract_content_hash") != _content_hash(payload):
            issues.append({"code": "contract_content_hash_mismatch"})
        return ValueGateValidationResult(
            governing_issues=_deduplicate_findings(issues),
            ambient_findings=(),
        )
    for key in sorted(LEGACY_POSITIVE_KEYS & set(payload)):
        issues.append({"code": "legacy_positive_key_forbidden", "key": key})
    denominators = payload.get("denominators")
    if not isinstance(denominators, Mapping):
        issues.append({"code": "denominators_missing"})
    else:
        expected_denominators = _candidate_catalog_denominators_cached()
        provenance_result = _catalog_provenance_validation_result(
            denominators.get("catalog_provenance"),
            expected_denominators["catalog_provenance"],
            denominator_fields=frozenset(expected_denominators) - {"catalog_provenance"},
        )
        provenance_issues = provenance_result.governing_issues
        issues.extend(provenance_issues)
        ambient_findings.extend(provenance_result.ambient_findings)
        modes = tuple(denominators.get("evaluation_modes") or ())
        if modes != tuple(get_args(ValueEvaluationMode)):
            issues.append({"code": "evaluation_mode_denominator_not_full"})
        statuses = tuple(denominators.get("identification_statuses") or ())
        if statuses != ("point", "partial", "proxy"):
            issues.append({"code": "identification_status_denominator_not_full"})
        if not provenance_issues and any(
            denominators.get(field) != expected_denominators[field]
            for field in (
                "registered_method_count",
                "catalog_entry_count",
                "catalog_matches_registry",
                "catalog_snapshot_id",
                "catalog_snapshot_stable",
            )
        ):
            issues.append({"code": "catalog_method_denominator_drift"})
        methods = tuple(denominators.get("value_capable_methods") or ())
        expected_methods = tuple(expected_denominators["value_capable_methods"])
        if not provenance_issues and (
            denominators.get("value_capable_method_count")
            != expected_denominators["value_capable_method_count"]
            or methods != expected_methods
        ):
            issues.append({"code": "value_capability_denominator_drift"})
        encoded = json.dumps(
            methods,
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if denominators.get("value_capable_fqn_set_hash") != (
            "sha256:" + hashlib.sha256(encoded).hexdigest()
        ):
            issues.append({"code": "value_capability_set_hash_mismatch"})
        if tuple(denominators.get("native_contract_families") or ()) != (NATIVE_CONTRACT_FAMILIES):
            issues.append({"code": "native_contract_family_denominator_drift"})
    expected_methods = tuple(
        denominators.get("value_capable_methods") or () if isinstance(denominators, Mapping) else ()
    )
    production = payload.get("production_refusal")
    if not isinstance(production, Mapping):
        issues.append({"code": "production_refusal_missing"})
    else:
        issues.extend(_validate_first_vertical_data_gap_receipt(production))
        if production.get("status") == "value_ready" or production.get("value_receipt") is not None:
            issues.append({"code": "fabricated_production_value_ready"})
    acquisition = payload.get("acquisition_routing")
    if not isinstance(acquisition, Mapping):
        issues.append({"code": "value_input_acquisition_route_missing"})
    else:
        issues.extend(_validate_acquisition_routing(acquisition))
    education = payload.get("education_refusal")
    if not isinstance(education, Mapping):
        issues.append({"code": "education_refusal_missing"})
    else:
        issues.extend(
            _validate_refusal_receipt(
                education,
                expected_kind="education_estimand_binding_refusal",
                expected_blocker="method_estimand_binding_mismatch",
                expected_acquisition=None,
                expected_methods=expected_methods,
            )
        )
        if education.get("status") == "value_ready" or education.get("value_receipt") is not None:
            issues.append({"code": "fabricated_education_value_ready"})
    proofs = payload.get("native_projector_contract_proofs")
    if not isinstance(proofs, list):
        issues.append({"code": "native_projector_contract_proofs_missing"})
    else:
        issues.extend(_validate_native_projection_proofs(proofs))
    refusals = payload.get("projector_refusal_proofs")
    if not isinstance(refusals, list):
        issues.append({"code": "projector_refusal_proofs_missing"})
    else:
        issues.extend(_validate_projector_refusal_proofs(refusals))
    transport = payload.get("transport_component_proofs")
    if not isinstance(transport, Mapping):
        issues.append({"code": "transport_component_proofs_missing"})
    else:
        issues.extend(_validate_transport_component_proofs(transport))
        first_transport = transport.get("first_vertical")
        if isinstance(production, Mapping) and isinstance(first_transport, Mapping):
            owner_availability = production.get("owner_availability")
            if (
                first_transport.get("candidate_id") != production.get("candidate_id")
                or first_transport.get("candidate_content_hash")
                != production.get("candidate_content_hash")
                or first_transport.get("design_problem_ref") != production.get("design_problem_ref")
                or first_transport.get("world_model_record_id")
                != production.get("world_model_record_id")
                or first_transport.get("world_model_record_content_hash")
                != production.get("world_model_record_content_hash")
                or not isinstance(owner_availability, Mapping)
                or first_transport.get("query_outcome") != owner_availability.get("variable_id")
            ):
                issues.append({"code": "first_vertical_transport_receipt_unbound"})
    census = payload.get("fork_b_census_receipt")
    if not isinstance(census, Mapping):
        issues.append({"code": "fork_b_census_receipt_missing"})
    elif (
        census.get("fork") != "B"
        or census.get("authority") != "shadow_read_only_no_bind"
        or census.get("content_hash") != FORK_B_CENSUS_CONTENT_HASH
        or census.get("raw_full_table_content_hash") != FORK_B_CENSUS_RAW_HASH
        or census.get("numeric_identities") != 5124
        or census.get("relation_rows") != 13092
        or census.get("usable_certified_relations") != 0
    ):
        issues.append({"code": "fork_b_census_receipt_drift"})
    if "decisive_mutations" in payload:
        issues.append({"code": "self_attested_mutation_results_forbidden"})
    mutation_by_id = {
        row.get("mutation_id"): row
        for row in payload.get("decisive_mutation_expectations") or ()
        if isinstance(row, Mapping)
    }
    for mutation_id in EXPECTED_MUTATION_IDS:
        row = mutation_by_id.get(mutation_id)
        if row is None:
            issues.append({"code": "decisive_mutation_missing", "mutation_id": mutation_id})
        elif (
            row.get("expected_result") != "RED"
            or row.get("proof") != FROZEN_MUTATION_PROOFS[mutation_id]
            or "result" in row
            or "observed_result" in row
        ):
            issues.append(
                {"code": "decisive_mutation_expectation_invalid", "mutation_id": mutation_id}
            )
    source_harness = payload.get("source_flip_mutation_harness")
    if (
        not isinstance(source_harness, Mapping)
        or tuple(source_harness.get("mutation_ids") or ()) != SOURCE_FLIP_MUTATION_IDS
    ):
        issues.append({"code": "source_flip_mutation_denominator_drift"})
    volatile_paths = _volatile_content_paths(payload)
    for path in volatile_paths:
        issues.append({"code": "volatile_content_field", "path": path})
    expected_hash = _content_hash(payload)
    if payload.get("contract_content_hash") != expected_hash:
        issues.append({"code": "contract_content_hash_mismatch"})
    return ValueGateValidationResult(
        governing_issues=_deduplicate_findings(issues),
        ambient_findings=_deduplicate_findings(ambient_findings),
    )


def validate_payload(payload: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return governing N8 failures for backward-compatible owner consumers."""

    return validate_payload_result(payload).governing_issues


def _validate_refusal_receipt(
    receipt_payload: Mapping[str, Any],
    *,
    expected_kind: str,
    expected_blocker: str,
    expected_acquisition: str | None,
    expected_methods: tuple[str, ...],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    expected_hash = gy_content_hash(
        {key: value for key, value in receipt_payload.items() if key != "content_hash"}
    )
    if receipt_payload.get("content_hash") != expected_hash:
        issues.append({"code": "value_refusal_receipt_hash_mismatch"})
    if (
        receipt_payload.get("receipt_kind") != expected_kind
        or receipt_payload.get("status") != "value_blocked"
        or receipt_payload.get("decision_grade") != "blocked"
        or receipt_payload.get("authority_blockers") != [expected_blocker]
        or receipt_payload.get("value_receipt") is not None
        or receipt_payload.get("acquisition_requirement") != expected_acquisition
    ):
        issues.append(
            {
                "code": "value_refusal_terminal_incoherent",
                "receipt_kind": expected_kind,
            }
        )
    if _is_fixture_world_hash(receipt_payload.get("world_model_record_content_hash")):
        issues.append({"code": "value_refusal_fixture_world_hash"})
    selection_payload = receipt_payload.get("method_selection_receipt")
    if not isinstance(selection_payload, Mapping):
        issues.append({"code": "value_refusal_selection_receipt_missing"})
        return issues
    from polisyos.foundry.methods.selection import MethodSelectionReceipt

    try:
        selection = MethodSelectionReceipt.model_validate(selection_payload)
    except (ValidationError, ValueError) as exc:
        issues.append(
            {
                "code": "value_refusal_selection_receipt_invalid",
                "error": str(exc),
            }
        )
        return issues
    if selection.selection_authority != "foundry_registry_advisor":
        issues.append({"code": "value_refusal_selection_authority_invalid"})
    if tuple(selection.denominator) != expected_methods:
        issues.append({"code": "value_refusal_selection_denominator_drift"})
    if receipt_payload.get("selected_method_fqn") != selection.selected_method_fqn:
        issues.append({"code": "value_refusal_selected_method_mismatch"})
    return issues


def _validate_first_vertical_data_gap_receipt(
    receipt_payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    expected_hash = gy_content_hash(
        {key: value for key, value in receipt_payload.items() if key != "content_hash"}
    )
    if receipt_payload.get("content_hash") != expected_hash:
        issues.append({"code": "value_refusal_receipt_hash_mismatch"})
    if (
        receipt_payload.get("receipt_kind") != "first_vertical_owner_data_gap"
        or receipt_payload.get("status") != "value_blocked"
        or receipt_payload.get("decision_grade") != "blocked"
        or receipt_payload.get("authority_blockers") != ["acquire_data:value_panel_data_missing"]
        or receipt_payload.get("selection_stage") != "not_reached_owner_data_unavailable"
        or receipt_payload.get("selected_method_fqn") is not None
        or receipt_payload.get("method_selection_receipt") is not None
        or receipt_payload.get("value_data_profile_content_hash") is not None
        or receipt_payload.get("value_receipt") is not None
    ):
        issues.append({"code": "first_vertical_data_gap_terminal_incoherent"})
    availability = receipt_payload.get("owner_availability")
    if not isinstance(availability, Mapping):
        issues.append({"code": "first_vertical_owner_availability_missing"})
    elif (
        availability.get("variable_id") != "employment_retention"
        or availability.get("status") != "unavailable"
        or availability.get("dataset_count") != 0
        or availability.get("metric_binding_count") != 0
        or availability.get("observation_count") != 0
        or not availability.get("coverage_ref")
        or not availability.get("availability_content_hash")
    ):
        issues.append({"code": "first_vertical_owner_availability_incoherent"})
    if (
        receipt_payload.get("k_world_ref_before")
        != receipt_payload.get("world_model_record_content_hash")
        or receipt_payload.get("k_world_ref_after")
        != receipt_payload.get("world_model_record_content_hash")
        or _is_fixture_world_hash(receipt_payload.get("world_model_record_content_hash"))
    ):
        issues.append({"code": "first_vertical_world_binding_incoherent"})
    world_binding = receipt_payload.get("world_binding")
    if not isinstance(world_binding, Mapping) or world_binding.get(
        "world_model_record_content_hash"
    ) != receipt_payload.get("world_model_record_content_hash"):
        issues.append({"code": "first_vertical_world_binding_unresolved"})
    return issues


def _validate_acquisition_routing(receipt: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    expected_hash = gy_content_hash(
        {key: value for key, value in receipt.items() if key != "content_hash"}
    )
    if receipt.get("content_hash") != expected_hash:
        issues.append({"code": "value_input_acquisition_route_hash_mismatch"})
    if (
        receipt.get("terminal_kind") != "acquisition_required"
        or receipt.get("acquisition_receipt") is not None
        or receipt.get("simulated_reentry") is not False
    ):
        issues.append({"code": "value_input_acquisition_route_incoherent"})
    gap_payload = receipt.get("requirement_gap")
    if not isinstance(gap_payload, Mapping):
        issues.append({"code": "value_input_acquisition_gap_missing"})
        return issues
    from polisyos.runtime.quality.acquisition_planner import AcquisitionRequirementGap

    try:
        gap = AcquisitionRequirementGap.model_validate(gap_payload)
    except (ValidationError, ValueError) as exc:
        issues.append({"code": "value_input_acquisition_gap_invalid", "error": str(exc)})
        return issues
    binding = gap.metadata.get("candidate_binding")
    availability = gap.metadata.get("availability")
    if (
        gap.metadata.get("source") != "l1_dcat_variable_availability"
        or gap.metadata.get("satisfaction_status") != "unsatisfied"
        or not isinstance(binding, Mapping)
        or not isinstance(availability, Mapping)
        or binding.get("candidate_id") != receipt.get("selected_candidate_ref")
        or binding.get("candidate_content_hash") != receipt.get("selected_candidate_content_hash")
        or availability.get("variable_id") != "employment_retention"
    ):
        issues.append({"code": "value_input_acquisition_gap_unbound"})
    report = receipt.get("planner_report")
    if not isinstance(report, Mapping):
        issues.append({"code": "value_input_acquisition_planner_report_missing"})
        return issues
    records = report.get("acquisition_records")
    record = records[0] if isinstance(records, list) and len(records) == 1 else None
    if (
        report.get("status") != "pass"
        or not isinstance(record, Mapping)
        or record.get("requirement_gap_ref") != gap.requirement_gap_id
        or record.get("compiled_requirement_ref") != gap.compiled_requirement_ref
        or record.get("claim_ref") != gap.claim_ref
        or record.get("recommended_strategy") != "production_snapshot_build"
        or record.get("terminal_disposition") != "acquire"
        or record.get("status") != "ready"
        or record.get("producer_output_ref") != gap.producer_output_ref
    ):
        issues.append({"code": "value_input_acquisition_planner_report_incoherent"})
    return issues


def _validate_native_projection_proofs(
    proofs: list[Any],
) -> list[dict[str, Any]]:
    from polisyos.foundry.methods.components.value_evidence import (
        MethodValueEvidence,
        project_method_value_evidence,
        resolve_method_value_projection_capability,
    )

    issues: list[dict[str, Any]] = []
    cases_by_digest = {
        signature.stable_digest(): (report, signature, estimand)
        for report, signature, estimand in _native_projection_cases()
    }
    owner_families: list[str] = []
    for _report, signature, _estimand in cases_by_digest.values():
        capability = resolve_method_value_projection_capability(
            method_signature=signature,
            selected_output_slot="result",
        )
        if capability is None:
            issues.append(
                {
                    "code": "native_projector_owner_capability_unresolved",
                    "method_fqn": signature.fqn,
                }
            )
            continue
        owner_families.append(capability.projection_kind.value)
    if tuple(owner_families) != NATIVE_CONTRACT_FAMILIES:
        issues.append({"code": "native_projector_owner_denominator_drift"})
    presented_families = tuple(str(row.get("family")) for row in proofs if isinstance(row, Mapping))
    if presented_families != tuple(owner_families):
        issues.append({"code": "native_projector_family_denominator_drift"})
    forbidden = {
        "value_outer_set",
        "value_gate_receipt",
        "value_ref",
        "promotion_decision",
    }
    for proof in proofs:
        if not isinstance(proof, Mapping):
            issues.append({"code": "native_projector_proof_invalid_shape"})
            continue
        family = str(proof.get("family"))
        if forbidden & set(proof):
            issues.append(
                {"code": "contract_projection_contains_production_carrier", "family": family}
            )
        if (
            proof.get("authority_scope") != "contract_only_nonproduction"
            or proof.get("production_value_eligible") is not False
            or not str(proof.get("status") or "").startswith("contract_projection_")
        ):
            issues.append(
                {"code": "contract_projection_claimed_production_authority", "family": family}
            )
        expected_hash = gy_content_hash(
            {key: value for key, value in proof.items() if key != "proof_content_hash"}
        )
        if proof.get("proof_content_hash") != expected_hash:
            issues.append({"code": "native_projector_proof_hash_mismatch", "family": family})
        model_payload = {
            key: value
            for key, value in proof.items()
            if key not in {"family", "proof_scope", "native_interval_width", "proof_content_hash"}
        }
        try:
            evidence = MethodValueEvidence.model_validate(model_payload)
        except (ValidationError, ValueError) as exc:
            issues.append(
                {
                    "code": "native_projector_evidence_invalid",
                    "family": family,
                    "error": str(exc),
                }
            )
            continue
        case = cases_by_digest.get(evidence.method_signature_digest)
        if case is None:
            issues.append(
                {
                    "code": "native_projector_method_signature_unresolved",
                    "family": family,
                }
            )
            continue
        report, signature, estimand = case
        capability = resolve_method_value_projection_capability(
            method_signature=signature,
            selected_output_slot=evidence.selected_output_slot,
        )
        if (
            capability is None
            or capability != evidence.native_projection_capability
            or family != capability.projection_kind.value
            or evidence.method_fqn != signature.fqn
        ):
            issues.append({"code": "native_projector_owner_witness_mismatch", "family": family})
            continue
        expected = project_method_value_evidence(
            method_signature=signature,
            method_result=_contract_method_result(report),
            estimand=estimand,
            selected_output_slot=evidence.selected_output_slot,
            projection_binding=_projection_binding(report, signature, estimand),
        )
        if not isinstance(expected, MethodValueEvidence) or expected != evidence:
            issues.append({"code": "native_projector_owner_rederive_drift", "family": family})
        interval = tuple(evidence.envelope.confidence_interval or ())
        expected_width = interval[1] - interval[0] if len(interval) == 2 else None
        if proof.get("native_interval_width") != expected_width:
            issues.append({"code": "native_projector_width_not_native", "family": family})
    return issues


def _validate_projector_refusal_proofs(proofs: list[Any]) -> list[dict[str, Any]]:
    from polisyos.foundry.methods.components.value_evidence import MethodValueRefusal

    issues: list[dict[str, Any]] = []
    expected_cases = (
        "unverified_truthfulness",
        "wrong_treatment_identity",
        "undeclared_capability",
    )
    cases = tuple(str(row.get("case_id")) for row in proofs if isinstance(row, Mapping))
    if cases != expected_cases:
        issues.append({"code": "projector_refusal_denominator_drift"})
    for proof in proofs:
        if not isinstance(proof, Mapping):
            issues.append({"code": "projector_refusal_invalid_shape"})
            continue
        expected_hash = gy_content_hash(
            {key: value for key, value in proof.items() if key != "proof_content_hash"}
        )
        if proof.get("proof_content_hash") != expected_hash:
            issues.append({"code": "projector_refusal_hash_mismatch"})
        try:
            MethodValueRefusal.model_validate(
                {
                    key: value
                    for key, value in proof.items()
                    if key not in {"case_id", "proof_content_hash"}
                }
            )
        except (ValidationError, ValueError) as exc:
            issues.append({"code": "projector_refusal_invalid", "error": str(exc)})
    return issues


def _validate_transport_component_proofs(
    proofs: Mapping[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if set(proofs) != {"first_vertical", "education", "unseen_pack_shape"}:
        issues.append({"code": "transport_component_denominator_drift"})
    for role in ("first_vertical", "education", "unseen_pack_shape"):
        proof = proofs.get(role)
        if not isinstance(proof, Mapping):
            issues.append({"code": "transport_component_proof_missing", "role": role})
            continue
        expected_hash = gy_content_hash(
            {key: value for key, value in proof.items() if key != "proof_content_hash"}
        )
        if proof.get("proof_content_hash") != expected_hash:
            issues.append({"code": "transport_component_proof_hash_mismatch", "role": role})
        if proof.get("production_value_eligible") is not False:
            issues.append({"code": "transport_component_claimed_value_authority", "role": role})
        if (
            proof.get("component_scope_only") is not True
            or proof.get("value_gate_receipt") is not None
            or not proof.get("context_binding_hash")
            or not proof.get("cycle_substrate_context_content_hash")
            or not proof.get("design_problem_ref")
            or not proof.get("candidate_id")
            or not proof.get("candidate_content_hash")
            or not proof.get("world_model_record_id")
            or not proof.get("world_model_record_content_hash")
            or not proof.get("query_treatment")
            or not proof.get("query_outcome")
        ):
            issues.append({"code": "transport_component_proof_incoherent", "role": role})
        outcome_kind = proof.get("outcome_kind")
        if outcome_kind not in {"transport_receipt", "typed_refusal"}:
            issues.append({"code": "transport_component_outcome_kind_invalid", "role": role})
            continue

        covariates = proof.get("transport_covariates")
        if not isinstance(covariates, list):
            issues.append({"code": "transport_component_covariates_invalid", "role": role})
            covariates = []
        covariate_names = tuple(
            str(row.get("canonical_var") or "") for row in covariates if isinstance(row, Mapping)
        )
        if len(covariate_names) != len(covariates) or (
            covariate_names and len(set(covariate_names)) != len(covariate_names)
        ):
            issues.append({"code": "transport_component_covariates_invalid", "role": role})

        if outcome_kind == "typed_refusal":
            refusal = proof.get("typed_refusal")
            if (
                proof.get("transport_receipt") is not None
                or proof.get("transport_result_content_hash") is not None
                or not isinstance(refusal, Mapping)
                or not refusal.get("code")
            ):
                issues.append({"code": "transport_component_refusal_invalid", "role": role})
            if (
                isinstance(refusal, Mapping)
                and refusal.get("code") == "acquire_data:transport_context_unresolved"
                and (
                    covariates
                    or proof.get("selection_diagram_content_hash") is not None
                    or proof.get("selection_nodes") != []
                )
            ):
                issues.append(
                    {"code": "transport_component_context_refusal_incoherent", "role": role}
                )
            continue

        receipt_payload = proof.get("transport_receipt")
        try:
            receipt = ValueTransportReceipt.model_validate(receipt_payload)
        except (ValidationError, ValueError) as exc:
            issues.append(
                {
                    "code": "transport_component_receipt_invalid",
                    "role": role,
                    "error": str(exc),
                }
            )
            continue
        if proof.get("typed_refusal") is not None:
            issues.append({"code": "transport_component_receipt_has_refusal", "role": role})
        if not covariates or not proof.get("selection_diagram_content_hash"):
            issues.append({"code": "transport_component_covariates_invalid", "role": role})
        if receipt.world_model_record_id != proof.get(
            "world_model_record_id"
        ) or receipt.world_model_record_content_hash != proof.get(
            "world_model_record_content_hash"
        ):
            issues.append({"code": "transport_component_world_binding_mismatch", "role": role})
        if tuple(proof.get("required_target_data") or ()) != receipt.required_target_data:
            issues.append({"code": "transport_component_required_data_mismatch", "role": role})
        receipt_dump = receipt.model_dump(mode="json")
        if proof.get("transport_result_content_hash") != gy_content_hash(receipt_dump):
            issues.append({"code": "transport_component_receipt_hash_mismatch", "role": role})
        nodes = proof.get("selection_nodes")
        if not isinstance(nodes, list) or len(nodes) != len(covariates):
            issues.append({"code": "transport_component_selection_nodes_invalid", "role": role})
            continue
        covariates_by_name = {
            str(row.get("canonical_var")): row for row in covariates if isinstance(row, Mapping)
        }
        for node in nodes:
            if not isinstance(node, Mapping):
                issues.append({"code": "transport_component_selection_nodes_invalid", "role": role})
                continue
            row = covariates_by_name.get(str(node.get("target_variable")))
            if row is None or (
                node.get("source_ref") != row.get("source_row_content_hash")
                or node.get("target_ref") != row.get("target_row_content_hash")
                or node.get("source_value") != row.get("source_value")
                or node.get("target_value") != row.get("target_value")
            ):
                issues.append({"code": "transport_component_selection_nodes_invalid", "role": role})
    return issues


def _volatile_content_paths(value: Any, *, prefix: str = "") -> list[str]:
    forbidden_keys = {
        "wall_time_ms",
        "generated_at",
        "created_at",
        "timestamp",
        "elapsed_seconds",
    }
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key in forbidden_keys:
                paths.append(path)
            paths.extend(_volatile_content_paths(child, prefix=path))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            paths.extend(_volatile_content_paths(child, prefix=f"{prefix}[{index}]"))
    return paths


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _catalog_provenance_reissue_payload(
    recorded: Mapping[str, Any],
    live_denominators: Mapping[str, Any],
    live_ambient_manifest_content: Mapping[str, Any],
) -> dict[str, Any]:
    """Reissue catalog provenance and its P29 witness after sibling equality."""

    payload = json.loads(json.dumps(recorded))
    recorded_denominators = payload.get("denominators")
    if not isinstance(recorded_denominators, dict):
        raise ValueError("catalog_provenance_reissue_denominators_missing")
    live_copy = json.loads(json.dumps(live_denominators))
    live_provenance = live_copy.get("catalog_provenance")
    if not isinstance(live_provenance, dict):
        raise ValueError("catalog_provenance_reissue_live_member_missing")
    recorded_provenance = recorded_denominators.get("catalog_provenance")
    if not isinstance(recorded_provenance, dict):
        raise ValueError("catalog_provenance_reissue_recorded_member_missing")
    recorded_siblings = {
        key: value for key, value in recorded_denominators.items() if key != "catalog_provenance"
    }
    live_siblings = {key: value for key, value in live_copy.items() if key != "catalog_provenance"}
    if recorded_siblings != live_siblings:
        changed_fields = sorted(
            key
            for key in set(recorded_siblings) | set(live_siblings)
            if recorded_siblings.get(key) != live_siblings.get(key)
        )
        raise ValueError("catalog_provenance_reissue_denominator_drift:" + "|".join(changed_fields))
    source_flip_harness = payload.get("source_flip_mutation_harness")
    if not isinstance(source_flip_harness, dict):
        raise ValueError("catalog_provenance_reissue_source_flip_harness_missing")
    recorded_mutation_ids = tuple(source_flip_harness.get("mutation_ids") or ())
    historical_mutation_ids = tuple(
        mutation_id
        for mutation_id in SOURCE_FLIP_MUTATION_IDS
        if mutation_id != EDITABLE_DIRECT_URL_SOURCE_FLIP_ID
    )
    if recorded_mutation_ids not in {
        historical_mutation_ids,
        SOURCE_FLIP_MUTATION_IDS,
    }:
        raise ValueError("catalog_provenance_reissue_source_flip_denominator_drift")

    expected_provenance = json.loads(json.dumps(recorded_provenance))
    recorded_ambient = expected_provenance.get("ambient_discovery")
    live_ambient = live_provenance.get("ambient_discovery")
    if not isinstance(recorded_ambient, dict) or not isinstance(live_ambient, dict):
        raise ValueError("catalog_provenance_reissue_ambient_manifest_missing")
    recorded_entries = recorded_ambient.get("entry_points")
    live_entries = live_ambient.get("entry_points")
    if not isinstance(recorded_entries, list) or not isinstance(live_entries, list):
        raise ValueError("catalog_provenance_reissue_entry_points_missing")
    if len(recorded_entries) != len(live_entries):
        raise ValueError("catalog_provenance_reissue_unrelated_ambient_drift")
    frozen_entries = json.loads(json.dumps(recorded_entries))
    from polisyos.core.components.discovery import (
        _component_discovery_manifest_id,
    )

    live_manifest_content = json.loads(json.dumps(live_ambient_manifest_content))
    live_manifest_entries = live_manifest_content.get("entry_points")
    if live_manifest_entries != live_entries:
        raise ValueError("catalog_provenance_reissue_manifest_evidence_mismatch")
    live_manifest_id = _component_discovery_manifest_id(live_manifest_content)
    if live_manifest_id != live_ambient.get("manifest_id"):
        raise ValueError("catalog_provenance_reissue_manifest_evidence_mismatch")
    historical_manifest_content = json.loads(json.dumps(live_manifest_content))
    historical_manifest_entries = historical_manifest_content["entry_points"]
    for recorded_entry, live_entry in zip(recorded_entries, live_entries, strict=True):
        if not isinstance(recorded_entry, dict) or not isinstance(live_entry, dict):
            raise ValueError("catalog_provenance_reissue_entry_point_invalid")
        if recorded_entry.get("editable_install") is True:
            if (
                live_entry.get("editable_install") is not True
                or live_entry.get("direct_url_sha256") is not None
            ):
                raise ValueError("catalog_provenance_reissue_editable_identity_drift")
            recorded_entry["direct_url_sha256"] = None
    for historical_entry, frozen_entry in zip(
        historical_manifest_entries,
        frozen_entries,
        strict=True,
    ):
        if not isinstance(historical_entry, dict) or not isinstance(frozen_entry, dict):
            raise ValueError("catalog_provenance_reissue_entry_point_invalid")
        if frozen_entry.get("editable_install") is True:
            historical_entry["direct_url_sha256"] = frozen_entry.get("direct_url_sha256")
    if _component_discovery_manifest_id(historical_manifest_content) != recorded_ambient.get(
        "manifest_id"
    ):
        raise ValueError("catalog_provenance_reissue_unrelated_ambient_drift")
    recorded_ambient["manifest_id"] = live_manifest_id
    from polisyos.foundry.methods.catalog.snapshot import (
        method_catalog_provenance_id,
    )

    expected_provenance["provenance_id"] = method_catalog_provenance_id(expected_provenance)
    if expected_provenance != live_provenance:
        raise ValueError("catalog_provenance_reissue_unrelated_ambient_drift")

    recorded_denominators["catalog_provenance"] = expected_provenance
    source_flip_harness["mutation_ids"] = list(SOURCE_FLIP_MUTATION_IDS)
    payload["contract_content_hash"] = _content_hash(payload)
    return payload


def check_catalog_provenance(
    repo_root: Path,
    *,
    expected_source_freeze: str | None = None,
) -> tuple[dict[str, Any], ...]:
    """Validate the frozen payload against live canonical catalog provenance."""

    return check_catalog_provenance_result(
        repo_root,
        expected_source_freeze=expected_source_freeze,
    ).governing_issues


def check_catalog_provenance_result(
    repo_root: Path,
    *,
    expected_source_freeze: str | None = None,
) -> ValueGateValidationResult:
    """Validate frozen catalog provenance and retain ambient diagnostics."""

    path = repo_root / OUTPUT_PATH
    if not path.exists():
        return ValueGateValidationResult(
            governing_issues=({"code": "artifact_missing", "path": OUTPUT_PATH},),
            ambient_findings=(),
        )
    return validate_payload_result(
        _load_json(path),
        expected_source_freeze=expected_source_freeze,
    )


def check(
    repo_root: Path,
    *,
    expected_source_freeze: str | None = None,
) -> tuple[dict[str, Any], ...]:
    """Return governing full-contract failures for legacy callers."""

    return check_result(
        repo_root,
        expected_source_freeze=expected_source_freeze,
    ).governing_issues


def check_result(
    repo_root: Path,
    *,
    expected_source_freeze: str | None = None,
) -> ValueGateValidationResult:
    """Compare the full frozen N8 contract through its governed projection."""

    path = repo_root / OUTPUT_PATH
    if not path.exists():
        return ValueGateValidationResult(
            governing_issues=({"code": "artifact_missing", "path": OUTPUT_PATH},),
            ambient_findings=(),
        )
    if expected_source_freeze is None:
        return ValueGateValidationResult(
            governing_issues=({"code": "catalog_dependency_source_freeze_not_supplied"},),
            ambient_findings=(),
        )
    expected = build_payload(
        repo_root,
        expected_source_freeze=expected_source_freeze,
    )
    actual = _load_json(path)
    result = validate_payload_result(
        actual,
        expected_source_freeze=expected_source_freeze,
    )
    issues = list(result.governing_issues)
    try:
        artifact_drift = _governed_value_gate_projection(actual) != _governed_value_gate_projection(
            expected
        )
    except (RuntimeError, TypeError, ValueError):
        artifact_drift = True
    if artifact_drift:
        issues.append({"code": "artifact_drift", "path": OUTPUT_PATH})
    return ValueGateValidationResult(
        governing_issues=_deduplicate_findings(issues),
        ambient_findings=result.ambient_findings,
    )


def corrupt_field_drift_check(
    repo_root: Path,
    *,
    expected_source_freeze: str,
) -> int:
    base = build_payload(
        repo_root,
        expected_source_freeze=expected_source_freeze,
    )
    cases: list[tuple[str, dict[str, Any], str]] = []

    promoted = json.loads(json.dumps(base))
    promoted["status"] = "value_ready"
    promoted["contract_content_hash"] = _content_hash(promoted)
    cases.append(
        (
            "dependency_status_promoted",
            promoted,
            "catalog_dependency_status_promoted",
        )
    )

    forged_code = json.loads(json.dumps(base))
    forged_authority = forged_code["catalog_dependency_authority"]
    if forged_authority["result_kind"] == "runtime_cutoff_not_established":
        forged_failure = forged_authority["preflight_refusal"]["failure"]
    else:
        forged_failure = forged_authority["failure"]
    forged_failure["failure_code"] = "dependency_environment_receipt_not_established"
    forged_code["contract_content_hash"] = _content_hash(forged_code)
    cases.append(
        (
            "dependency_failure_code_forged",
            forged_code,
            "catalog_dependency_authority_invalid",
        )
    )

    wrong_freeze = json.loads(json.dumps(base))
    wrong_authority = wrong_freeze["catalog_dependency_authority"]
    if wrong_authority["result_kind"] == "runtime_cutoff_not_established":
        wrong_request = wrong_authority["preflight_refusal"]["request"]["pre_source_request"]
    elif wrong_authority["result_kind"] == "source_rejected":
        wrong_request = wrong_authority["request"]["pre_source_request"]
    else:
        wrong_request = wrong_authority["request"]
    wrong_request["expected_source_freeze_commit"] = "0" * 40
    wrong_freeze["contract_content_hash"] = _content_hash(wrong_freeze)
    cases.append(
        (
            "dependency_source_freeze_substituted",
            wrong_freeze,
            "catalog_dependency_source_freeze_mismatch",
        )
    )

    results = []
    for case_id, payload, expected_code in cases:
        issues = validate_payload_result(
            payload,
            expected_source_freeze=expected_source_freeze,
        ).governing_issues
        codes = {str(issue.get("code")) for issue in issues}
        results.append(
            {
                "case_id": case_id,
                "expected_code": expected_code,
                "observed_codes": sorted(codes),
                "rejected": expected_code in codes,
            }
        )
    if all(result["rejected"] for result in results):
        print(
            "corrupt-field drift check: PASS corruptions rejected "
            + json.dumps(results, sort_keys=True)
        )
        return 1
    print(
        "corrupt-field drift check: FAIL corruption survived " + json.dumps(results, sort_keys=True)
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--check-catalog-provenance", action="store_true")
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--reissue-catalog-provenance", action="store_true")
    modes.add_argument("--corrupt-field-drift-check", action="store_true")
    modes.add_argument("--rederive-audit", action="store_true")
    modes.add_argument("--source-flip-mutations", action="store_true")
    parser.add_argument("--expected-source-freeze", required=True)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    repo_root = _repo_root()
    _ensure_src_path(repo_root)
    if args.corrupt_field_drift_check:
        return corrupt_field_drift_check(
            repo_root,
            expected_source_freeze=args.expected_source_freeze,
        )
    if args.rederive_audit:
        result = run_rederive_audit_result(
            repo_root,
            expected_source_freeze=args.expected_source_freeze,
        )
        if result.governing_issues:
            print(
                json.dumps(
                    {
                        "issues": list(result.governing_issues),
                        "ambient_findings": list(result.ambient_findings),
                    },
                    sort_keys=True,
                )
            )
            return 1
        return 0
    if args.source_flip_mutations:
        results = run_source_flip_mutations(repo_root)
        failures = tuple(row for row in results if row.get("result") != "RED")
        print(json.dumps({"results": list(results)}, sort_keys=True))
        return 1 if failures else 0
    if args.check_catalog_provenance:
        result = check_catalog_provenance_result(
            repo_root,
            expected_source_freeze=args.expected_source_freeze,
        )
        if result.governing_issues:
            print(
                json.dumps(
                    {
                        "status": "fail",
                        "issues": list(result.governing_issues),
                        "ambient_findings": list(result.ambient_findings),
                    },
                    sort_keys=True,
                )
            )
            return 1
        print(
            json.dumps(
                {
                    "status": "pass",
                    "path": OUTPUT_PATH,
                    "scope": "catalog_provenance",
                    "ambient_findings": list(result.ambient_findings),
                },
                sort_keys=True,
            )
        )
        return 0
    if args.reissue_catalog_provenance:
        print(
            json.dumps(
                {
                    "status": "not_established",
                    "code": "catalog_dependency_authority_not_established",
                },
                sort_keys=True,
            )
        )
        return 1
    if args.write:
        print(
            json.dumps(
                {
                    "status": "not_established",
                    "code": "catalog_dependency_authority_not_established",
                },
                sort_keys=True,
            )
        )
        return 1
    result = check_result(
        repo_root,
        expected_source_freeze=args.expected_source_freeze,
    )
    if result.governing_issues:
        print(
            json.dumps(
                {
                    "status": "fail",
                    "issues": list(result.governing_issues),
                    "ambient_findings": list(result.ambient_findings),
                },
                sort_keys=True,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "status": "pass",
                "path": OUTPUT_PATH,
                "ambient_findings": list(result.ambient_findings),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(
        run_timed_entrypoint(
            main,
            script_path=__file__,
            argv=sys.argv[1:],
            started_perf_counter=_TIMING_STARTED_AT,
        )
    )
