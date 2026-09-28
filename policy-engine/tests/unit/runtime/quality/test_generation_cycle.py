from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any, get_args
from uuid import uuid4

import pytest

import polisyos.runtime.quality.generation_cycle as generation_cycle_module
import polisyos.runtime.quality.promotion_sequence as promotion_sequence_module
from polisyos.core import canon
from polisyos.core import contracts as core_contracts
from polisyos.core.artifacts import ArtifactWriteOptions, FileSystemCAS
from polisyos.core.contracts.value_outer_set import DataTrust, ValueOuterSet
from polisyos.data_requirement import (
    DataQualityMinimums,
    DataRequirementScope,
    DataRequirementSpec,
)
from polisyos.data_requirement.compiler import compile_data_requirements_for_scenario
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality import confidence_ledger as confidence_ledger_module
from polisyos.runtime.quality import epoch_validity_cascade as epoch_cascade_module
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionCaptureProvenance,
    AcquisitionOwnerArtifact,
    AcquisitionWorldSnapshot,
    RecordedAcquisitionOwnerGateway,
    l1_variable_availability_requirement_gap,
    value_input_world_knowledge_requirement_gap,
)
from polisyos.runtime.quality.confidence_ledger import (
    LoadedDeploymentIdentityObservation,
)
from polisyos.runtime.quality.cycle_substrate import (
    CandidateLeverEvidence,
    CycleSubstrateContext,
    build_cycle_substrate_context,
    cycle_substrate_context_binding_hash,
    resolve_cycle_substrate_world_identity,
)
from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
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
    AcquisitionOverlayReentryReceipt,
    CandidateGroundingObservation,
    CandidateSummary,
    GenerationCycleController,
    GenerationCycleError,
    GenerationCycleRun,
    JointSimulationPort,
    N4GenerationPort,
    PendingN8ValuePort,
    PolicyGroundingPort,
    PromotionPortObservation,
    RealValueOwnerGateway,
    SimulationPortObservation,
    StrangleReceipt,
    ValueCalibrationReceipt,
    ValueGateReceipt,
    ValuePortObservation,
    ValueTransportReceipt,
    _apply_promotion_to_summaries,
    _build_boundary_world_model_record,
    _derive_fronts,
    _disposition_candidates,
    _grounding_disposition_denominator,
    _joint_simulation_port_outcome,
    _summary_with_value_observation,
    enforce_no_retry_without_new_grammar,
    generation_cycle_terminal_state,
    validate_generation_cycle_candidate_run,
    validate_generation_cycle_run,
)
from polisyos.runtime.quality.grounding_disposition_vocab import (
    GroundingDispositionKind,
)
from polisyos.runtime.quality.intervention_atom_binding import InterventionAtomBinding
from polisyos.runtime.quality.intervention_substrate import InterventionLeverRefusal
from polisyos.runtime.quality.open_world_risk import (
    OpenWorldRiskVectorArtifactRepository,
    PromotionRuntime,
    VerifiedOpenWorldRiskVector,
)
from polisyos.runtime.quality.promotion_sequence import (
    CanonicalN9PromotionPort,
    CanonicalPromotionReceipt,
    validate_canonical_promotion_receipt,
)
from polisyos.runtime.quality.substrate_registry import (
    SubstrateCoverage,
    SubstrateLayer,
    SubstrateRegistration,
    SubstrateRegistry,
    SubstrateSchemaRegime,
    SubstrateTrustTier,
    build_substrate_registry,
    build_substrate_registry_entry,
    default_substrate_catalog_paths,
)
from polisyos.runtime.quality.world_model_record import WorldModelRecordError
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.validation.decision_validity import DecisionValidityService
from tools.quality.validation import (
    check_layer3_gy_generation_cycle_contract as contract,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


def _canonical_loaded_deployment_identity() -> str:
    observation = confidence_ledger_module.capture_loaded_deployment_identity()
    assert observation.status == "established"
    assert observation.deployment_identity is not None
    return observation.deployment_identity


def _owner_catalog_prerequisite_issue(repo_root: Path) -> str | None:
    """Return actionable setup guidance when canonical owner catalogs are absent."""

    paths = default_substrate_catalog_paths(repo_root)
    required = (
        paths.root_manifest_path,
        paths.measurement_registry_path,
        paths.identification_mode_registry_path,
        paths.schema_regime_registry_path,
        paths.l1_dcat_path,
    )
    missing = tuple(path for path in required if not path.exists())
    if not missing:
        return None
    rendered = ", ".join(
        path.relative_to(repo_root).as_posix() if path.is_relative_to(repo_root) else path.as_posix()
        for path in missing
    )
    return (
        f"production_data owner catalog is unavailable ({rendered}); "
        "link the worktree's provisioned production_data owner tree read-only"
    )


_OWNER_CATALOG_GUIDANCE = (
    "production_data owner catalog is unavailable; "
    "link the worktree's provisioned production_data owner tree read-only"
)
_OWNER_CATALOG_PREREQUISITE_ISSUE = _owner_catalog_prerequisite_issue(REPO_ROOT)
_requires_owner_catalog = pytest.mark.skipif(
    _OWNER_CATALOG_PREREQUISITE_ISSUE is not None,
    reason=_OWNER_CATALOG_PREREQUISITE_ISSUE or _OWNER_CATALOG_GUIDANCE,
)


def test_grounding_disposition_denominator_derives_from_canonical_type() -> None:
    denominator = tuple(str(item) for item in get_args(GroundingDispositionKind))

    assert _grounding_disposition_denominator() == denominator
    assert contract._denominators()["grounding_dispositions"] == sorted(denominator)


def test_owner_catalog_prerequisite_is_declared_not_ambient(
    tmp_path: Path,
) -> None:
    """Every owner-backed semantic test declares the catalog it needs."""

    expected_names = {
        "test_acquisition_required_derives_n7_inputs_without_test_hints_and_reenters",
        "test_active_overlay_reentry_is_exact_direct_and_read_only",
        "test_cycle_world_identity_rejects_atom_from_another_problem",
        "test_cycle_world_identity_rejects_shaped_atom_even_when_strings_match",
        "test_default_value_port_binds_the_actual_n5_context",
        "test_explicit_joint_request_atom_refs_bind_before_injected_controller",
        "test_explicit_joint_request_cannot_bypass_context_wmr",
        "test_explicit_request_nested_atom_missing_slot_fails_world_identity",
        "test_joint_port_accepts_label_drift_after_atom_world_resolution",
        "test_joint_port_rejects_candidate_ref_mismatched_to_context_wmr",
        "test_joint_port_rejects_empty_atom_slots_as_unresolved_world_identity",
        "test_joint_port_reuses_exact_cycle_context_wmr",
        "test_joint_port_types_tampered_strict_atom_as_unresolved_world_identity",
        "test_shaped_wmr_ref_without_resolved_object_is_rejected",
    }
    declared_names = {
        name
        for name in expected_names
        if any(
            mark.name == "skipif"
            and "production_data owner catalog" in str(mark.kwargs.get("reason", ""))
            for mark in getattr(globals()[name], "pytestmark", ())
        )
    }

    assert declared_names == expected_names
    issue = _owner_catalog_prerequisite_issue(tmp_path)
    assert issue is not None
    assert "production_data owner catalog" in issue
    assert "link" in issue
    assert "read-only" in issue


def test_owner_catalog_prerequisite_skips_an_actual_node_when_catalog_is_absent(
    tmp_path: Path,
) -> None:
    """Prove the real collection path reports nonreceipt instead of semantic failure."""

    plugin_path = tmp_path / "missing_owner_catalog.py"
    plugin_path.write_text(
        """\
import os
from pathlib import Path

from polisyos.runtime.quality import substrate_registry

_real_paths = substrate_registry.default_substrate_catalog_paths
_missing_root = Path(os.environ["POLISYOS_TEST_MISSING_OWNER_ROOT"])


def _missing_paths(repo_root):
    del repo_root
    return _real_paths(_missing_root)


substrate_registry.default_substrate_catalog_paths = _missing_paths
""",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["POLISYOS_TEST_MISSING_OWNER_ROOT"] = str(tmp_path / "absent")
    environment["PYTHONPATH"] = os.pathsep.join(
        value
        for value in (str(tmp_path), str(REPO_ROOT), environment.get("PYTHONPATH", ""))
        if value
    )
    environment["PYTEST_PLUGINS"] = ",".join(
        value
        for value in (
            environment.get("PYTEST_PLUGINS", ""),
            "missing_owner_catalog",
        )
        if value
    )
    node_id = (
        "tests/unit/runtime/quality/test_generation_cycle.py::"
        "test_cycle_world_identity_rejects_shaped_atom_even_when_strings_match"
    )
    result = subprocess.run(  # noqa: S603 - lock-bound pytest with a local probe plugin.
        [sys.executable, "-m", "pytest", node_id, "-q", "-rs"],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[0].startswith("s")
    assert "production_data owner catalog is unavailable" in result.stdout
    assert "link the worktree's provisioned production_data owner tree read-only" in result.stdout


@dataclass(frozen=True)
class _Atom:
    intervention_id: str
    content_hash: str
    status: str = "candidate_unverified"
    world_model_record_ref: str | None = "world_model_record_test"
    target_world_slots: tuple[str, ...] = ("firm_survival",)
    problem_frame_ref: str | None = None


@dataclass(frozen=True)
class _Candidate:
    candidate_id: str
    atom: _Atom | InterventionAtomBinding
    diversity_key: tuple[str, str, str, str]
    status: str = "candidate_unverified"


@dataclass(frozen=True)
class _Ranking:
    candidate_id: str
    score: float
    voi_estimate: float
    trust_level: str = "search_guiding"
    promotion_allowed: bool = False


@dataclass(frozen=True)
class _GenerationResult:
    status: str
    candidates: tuple[_Candidate, ...]
    surrogate_rankings: tuple[_Ranking, ...]
    grounding_dispositions: tuple[Any, ...] = ()
    design_problem_ref: str | None = None


@dataclass(frozen=True)
class _CertificateChain:
    cg1_certificate_id: str = "cg1_cert_test"
    cg1_content_hash: str = "sha256:" + "a" * 64
    cg2_certificate_id: str = "cg2_cert_test"
    cg2_content_hash: str = "sha256:" + "b" * 64
    cg3_certificate_id: str = "cg3_cert_test"
    cg3_content_hash: str = "sha256:" + "c" * 64
    cg4_proxy_gap_risk_id: str | None = None
    cg4_proxy_gap_content_hash: str | None = None
    cg4_quarantine_handoff_id: str | None = None
    cg4_quarantine_handoff_hash: str | None = None
    cg5_action_certificate_id: str | None = None
    cg5_action_content_hash: str | None = None
    cg5_ticket_id: str | None = None
    cg5_ticket_hash: str | None = None


@dataclass(frozen=True)
class _GroundingDisposition:
    proposal_id: str
    candidate_id: str | None
    raw_candidate_hash: str
    disposition: str
    selected_relation: str
    shadow_atom_content_hash: str | None = None
    identified_atom_id: str | None = "atom_test"
    cg2_decision: str | None = "shadow_frozen"
    cg2_reason: str | None = "cg2_frozen_until_cg6"
    cg3_decision: str | None = "shadow"
    cg3_reason: str | None = "cg3_shadow_only"
    rejected_cause: dict[str, Any] | None = None
    certificate_chain: _CertificateChain = _CertificateChain()
    bridge_missing_records: tuple[dict[str, Any], ...] = ()


class _CounterexampleAwareGenerator:
    def __init__(self, *, first_atom: InterventionAtomBinding | None = None) -> None:
        self.problems: list[DesignProblem] = []
        self._first_atom = first_atom

    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> _GenerationResult:
        self.problems.append(problem)
        grammar = tuple(problem.runtime_hints.get("generation_cycle_grammar", ()))
        if cycle_index == 0:
            candidates = (
                _Candidate(
                    candidate_id="candidate_cycle_1",
                    atom=(
                        self._first_atom
                        if self._first_atom is not None
                        else _Atom("candidate_cycle_1", "sha256:" + "1" * 64)
                    ),
                    diversity_key=("grant", "firms", "proxy_only", "baseline"),
                ),
            )
            rankings = (
                _Ranking(
                    candidate_id="candidate_cycle_1",
                    score=0.93,
                    voi_estimate=0.82,
                ),
            )
        elif "lever:grant:adversarial_validate:missing_supporting_data" in grammar:
            candidates = (
                _Candidate(
                    candidate_id="candidate_cycle_2",
                    atom=_Atom("candidate_cycle_2", "sha256:" + "2" * 64),
                    diversity_key=("grant", "firms", "grounding_repair", "data_bound"),
                ),
            )
            rankings = (
                _Ranking(
                    candidate_id="candidate_cycle_2",
                    score=0.31,
                    voi_estimate=0.41,
                ),
            )
        else:
            candidates = (
                _Candidate(
                    candidate_id="candidate_repeat",
                    atom=_Atom("candidate_repeat", "sha256:" + "1" * 64),
                    diversity_key=("grant", "firms", "proxy_only", "baseline"),
                ),
            )
            rankings = (
                _Ranking(
                    candidate_id="candidate_repeat",
                    score=0.93,
                    voi_estimate=0.82,
                ),
            )
        return _GenerationResult(
            status="generated",
            candidates=candidates,
            surrogate_rankings=rankings,
        )


class _SameCandidateNewBasisGenerator:
    """Return one candidate identity with a distinct content occurrence per cycle."""

    def __init__(self) -> None:
        self.problems: list[DesignProblem] = []

    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> _GenerationResult:
        self.problems.append(problem)
        candidate = _Candidate(
            candidate_id="candidate_same_subject",
            atom=_Atom(
                "candidate_same_subject",
                "sha256:" + ("1" if cycle_index == 0 else "2") * 64,
            ),
            diversity_key=("grant", "firms", "same_subject", f"cycle_{cycle_index}"),
        )
        return _GenerationResult(
            status="generated",
            candidates=(candidate,),
            surrogate_rankings=(
                _Ranking(
                    candidate_id=candidate.candidate_id,
                    score=0.93 if cycle_index == 0 else 0.31,
                    voi_estimate=0.82 if cycle_index == 0 else 0.41,
                ),
            ),
        )


class _AlwaysLowGrounding:
    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
        generation_result: Any | None = None,
    ) -> CandidateGroundingObservation:
        del problem, generation_result
        return CandidateGroundingObservation(
            candidate_id=str(candidate.candidate_id),
            status="grounding_gap",
            grounding_score=0.2 if cycle_index == 0 else 0.68,
            issue_codes=("missing_supporting_data",) if cycle_index == 0 else (),
            evidence_refs=() if cycle_index == 0 else ("evidence://supporting-data",),
            current_valid=False,
        )


class _StableShadowGrounding:
    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
        generation_result: Any | None = None,
    ) -> CandidateGroundingObservation:
        del problem, cycle_index, generation_result
        return CandidateGroundingObservation(
            candidate_id=str(candidate.candidate_id),
            status="grounded_shadow",
            grounding_score=0.8,
            evidence_refs=("evidence://b29/stable-shadow",),
            current_valid=False,
            report_ref="grounding://b29/stable-shadow",
            grounding_source="cgf_firewall",
            grounding_disposition="shadow_bound",
        )


class _CurrentValidGrounding:
    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
        generation_result: Any | None = None,
    ) -> CandidateGroundingObservation:
        del problem, cycle_index, generation_result
        return CandidateGroundingObservation(
            candidate_id=str(candidate.candidate_id),
            status="current_valid",
            grounding_score=0.95,
            evidence_refs=("evidence://b29/current-valid",),
            current_valid=True,
            report_ref="grounding://b29/current-valid",
            grounding_source="cgf_firewall",
            grounding_disposition="current_valid",
        )


class _CurrentValidRepairGrounding:
    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
        generation_result: Any | None = None,
    ) -> CandidateGroundingObservation:
        del problem, cycle_index, generation_result
        return CandidateGroundingObservation(
            candidate_id=str(candidate.candidate_id),
            status="current_valid",
            grounding_score=0.95,
            issue_codes=("missing_supporting_data",),
            evidence_refs=("evidence://b29/current-valid-repair",),
            current_valid=True,
            report_ref="grounding://b29/current-valid-repair",
            grounding_source="cgf_firewall",
            grounding_disposition="current_valid",
            quarantine_action="adversarial_validate",
        )


def _ready_value_observation(candidate_id: str) -> ValuePortObservation:
    """Build a small owner-shaped N8 receipt for terminal projection tests."""

    method_fqn = "causal.inference.did.standard@1.0.0"
    world_hash = "sha256:" + "d" * 64
    value_ref = "sha256:" + "e" * 64
    alternative = {
        "rank": 1,
        "method_fqn": method_fqn,
        "method_family": "causal_inference",
        "data_modalities": ["panel"],
        "advisor_score": None,
        "selected": True,
        "loss_reasons": [],
    }
    selection_payload = {
        "schema_version": "policyos.foundry.method_selection_receipt.v2",
        "selection_authority": "requested_registry_method",
        "selected_method_fqn": method_fqn,
        "ranked_alternatives": [alternative],
        "denominator": [method_fqn],
        "selection_context_hash": "sha256:" + "f" * 64,
    }
    selection_hash = "sha256:" + hashlib.sha256(
        json.dumps(
            selection_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()
    selection_receipt = generation_cycle_module.MethodSelectionReceipt.model_validate(
        {**selection_payload, "content_hash": selection_hash}
    )
    value_set = ValueOuterSet.interval_box(
        coordinates=("firm_survival",),
        lower=(1.0,),
        upper=(1.0,),
        identification_mode="point",
        assumptions=("b29_test",),
        assumption_status="externally_supported",
        calibration_scope={"scope": "unit"},
        data_trust=DataTrust(
            tier="unit",
            trust_cap=1.0,
            trust_multiplier=1.0,
            authority_ref="b29-test",
        ),
        world_model_record_ref=world_hash,
        epoch="2026",
        representation_status="certified",
    )
    transport = ValueTransportReceipt(
        status="direct",
        world_model_record_id="world_model_record_b29",
        world_model_record_content_hash=world_hash,
        transport_result_ref="sha256:" + "a" * 64,
        transport_status="identified",
        transport_mode="direct",
        identification_engine="b29-test",
    )
    calibration = ValueCalibrationReceipt(
        status="pass",
        forecast_tier="observable_calibrated",
        calibration_record_ref="s10://b29-test",
    )
    value_receipt = ValueGateReceipt(
        candidate_id=candidate_id,
        evaluation_mode="simulate_only",
        selected_method_fqn=method_fqn,
        method_selection_trace=(method_fqn,),
        identification_status=value_set.identification_status,
        value_outer_set=value_set,
        transport_receipt=transport,
        calibration_receipt=calibration,
        world_model_record_id="world_model_record_b29",
        world_model_record_content_hash=world_hash,
        value_ref=value_ref,
        wall_time_ms=1.0,
        wmr_cache_status="built",
        k_world_ref_before=world_hash,
        k_world_ref_after=world_hash,
    )
    return ValuePortObservation(
        status="value_ready",
        candidate_id=candidate_id,
        value_ref=value_ref,
        authority_blockers=(),
        reason="B29 owner-shaped value receipt for terminal projection.",
        evaluation_mode="simulate_only",
        selected_method_fqn=method_fqn,
        method_selection_receipt=selection_receipt,
        decision_grade="high",
        world_model_record_content_hash=world_hash,
        transport_receipt=transport,
        calibration_receipt=calibration,
        value_receipt=value_receipt,
    )


class _ReadyValuePort:
    def __call__(self, *, candidate: Any, **kwargs: Any) -> ValuePortObservation:
        del kwargs
        return _ready_value_observation(str(candidate.candidate_id))


class _BudgetExhaustedValuePort:
    def __call__(self, *, candidate: Any, **kwargs: Any) -> ValuePortObservation:
        del kwargs
        return ValuePortObservation(
            status="value_blocked",
            candidate_id=str(candidate.candidate_id),
            authority_blockers=("budget_exhausted_for_next_level",),
            reason="B29 controlled budget-stop fixture.",
            decision_grade="blocked",
        )


class _NoNewGrammarRevision:
    def __call__(self, **kwargs: Any) -> Any:
        prior_cycle = kwargs["prior_cycle"]
        return prior_cycle.revision_request.model_copy(
            update={
                "new_grammar_elements": (),
                "next_grammar_elements": prior_cycle.revision_request.previous_grammar_elements,
                "revised_problem": kwargs["problem"],
                "next_candidate_ref": prior_cycle.selected_candidate_ref,
            }
        )


class _ConstantStrategyRevision:
    def __call__(self, **kwargs: Any) -> Any:
        prior_cycle = kwargs["prior_cycle"]
        default = kwargs["default_revision"]
        return default.model_copy(
            update={
                "revision_strategy": "adversarial_validate",
                "strategy_payload": {
                    **default.strategy_payload,
                    "terminal_kind": "constant",
                },
                "new_grammar_elements": (
                    "lever:grant:adversarial_validate:missing_supporting_data",
                ),
                "next_grammar_elements": (
                    *prior_cycle.revision_request.previous_grammar_elements,
                    "lever:grant:adversarial_validate:missing_supporting_data",
                ),
            }
        )


class _AcquisitionGrounding:
    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
        generation_result: Any | None = None,
    ) -> CandidateGroundingObservation:
        del problem, cycle_index, generation_result
        return CandidateGroundingObservation(
            candidate_id=str(candidate.candidate_id),
            status="grounding_gap",
            grounding_score=0.1,
            issue_codes=("acquire_data:owner_panel_missing",),
            current_valid=False,
        )


class _EmptyGenerationPort:
    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> _GenerationResult:
        del problem, cycle_index
        return _GenerationResult(
            status="generation_unavailable", candidates=(), surrogate_rankings=()
        )


class _LegacyOnlyGenerationPort:
    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> _GenerationResult:
        del problem, cycle_index
        candidate = _Candidate(
            candidate_id="candidate_legacy_only",
            atom=_Atom("candidate_legacy_only", "sha256:" + "3" * 64),
            diversity_key=("grant", "firms", "legacy_matrix", "baseline"),
        )
        return _GenerationResult(
            status="generated",
            candidates=(candidate,),
            surrogate_rankings=(
                _Ranking(candidate_id=candidate.candidate_id, score=0.88, voi_estimate=0.4),
            ),
            grounding_dispositions=(),
        )


class _CgfGenerationPort:
    def __init__(
        self,
        *,
        missing_owner_target: bool = False,
        proxy_gap: bool = False,
        target_world_slots: tuple[str, ...] = ("firm_survival",),
    ) -> None:
        self._missing_owner_target = missing_owner_target
        self._proxy_gap = proxy_gap
        self._target_world_slots = target_world_slots

    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> _GenerationResult:
        del cycle_index
        problem_ref = gy_content_hash(problem.model_dump(mode="json"))
        candidate = _Candidate(
            candidate_id="candidate_cgf_shadow",
            atom=_Atom(
                "candidate_cgf_shadow",
                "sha256:" + "4" * 64,
                target_world_slots=() if self._missing_owner_target else self._target_world_slots,
                problem_frame_ref=problem_ref,
            ),
            diversity_key=("grant", "firms", "cgf_shadow", "baseline"),
        )
        chain = _CertificateChain(
            cg4_proxy_gap_risk_id="cg4_proxy_gap_deadbeefdeadbeef" if self._proxy_gap else None,
            cg4_proxy_gap_content_hash="sha256:" + "d" * 64 if self._proxy_gap else None,
            cg4_quarantine_handoff_id="cg4_quarantine_deadbeefdeadbeef"
            if self._proxy_gap
            else None,
            cg4_quarantine_handoff_hash="sha256:" + "e" * 64 if self._proxy_gap else None,
            cg5_action_certificate_id="cg5_action_deadbeefdeadbeef" if self._proxy_gap else None,
            cg5_action_content_hash="sha256:" + "f" * 64 if self._proxy_gap else None,
        )
        disposition = _GroundingDisposition(
            proposal_id="proposal.cgf_shadow",
            candidate_id=candidate.candidate_id,
            raw_candidate_hash="sha256:" + "5" * 64,
            disposition="shadow_bound",
            selected_relation="exact",
            shadow_atom_content_hash=candidate.atom.content_hash,
            certificate_chain=chain,
            bridge_missing_records=(
                {
                    "pattern": "bridge_missing",
                    "owner": "CG4",
                    "integration_status": "handoff_artifact_n6_direct_intake_not_wired",
                },
            )
            if self._proxy_gap
            else (),
        )
        return _GenerationResult(
            status="generated",
            candidates=(candidate,),
            surrogate_rankings=(
                _Ranking(candidate_id=candidate.candidate_id, score=0.91, voi_estimate=0.6),
            ),
            grounding_dispositions=(disposition,),
            design_problem_ref=problem_ref,
        )


class _DispositionOnlyGenerationPort:
    """Expose a real N4 non-binding denominator with no fabricated atom."""

    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> _GenerationResult:
        del cycle_index
        return _GenerationResult(
            status="generated",
            candidates=(),
            surrogate_rankings=(),
            grounding_dispositions=(
                _GroundingDisposition(
                    proposal_id="gy_n4.education_teaching_method",
                    candidate_id=None,
                    raw_candidate_hash="sha256:" + "7" * 64,
                    disposition="novel_cg3",
                    selected_relation="novel-candidate",
                    identified_atom_id=None,
                    cg2_decision="novel_candidate",
                    cg2_reason="cg2_relation_not_bind_eligible",
                    cg3_decision="route_to_acquisition",
                    cg3_reason="cg3_candidate_unbound",
                ),
            ),
            design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
        )


class _NoPromotionPort:
    def __call__(
        self,
        *,
        summaries: Any,
        problem: DesignProblem,
    ) -> PromotionPortObservation:
        del summaries, problem
        return PromotionPortObservation(
            status="not_promoted",
            reason="candidate_unbound",
        )


def test_production_n9_port_is_canonical_and_contract_fake_remains_available() -> None:
    """Production cannot route around identity admission; test fakes stay scoped."""

    class _RecordingPort:
        def __init__(self) -> None:
            self.call_count = 0

        def __call__(
            self,
            *,
            summaries: Any,
            problem: DesignProblem,
        ) -> PromotionPortObservation:
            del summaries, problem
            self.call_count += 1
            return PromotionPortObservation(
                status="not_promoted",
                reason="contract_fake_called",
            )

    fake = _RecordingPort()
    with pytest.raises(
        ValueError,
        match="production_promotion_port_must_be_container_derived",
    ):
        GenerationCycleController(promotion_port=fake)  # type: ignore[arg-type]

    production = GenerationCycleController()
    assert isinstance(production._promotion_port, CanonicalN9PromotionPort)
    # Exercise the runtime invariant as well as the constructor boundary.
    production._promotion_port = fake  # type: ignore[assignment]
    blocked = production._promote_completed_generation(
        summaries=(),
        problem=_problem("production_port_mutation_probe"),
        deployment_identity=None,
    )
    assert blocked.reason == "epoch_validity_refused:production_promotion_port_not_canonical"
    assert fake.call_count == 0

    contract_testing = GenerationCycleController(
        promotion_port=fake,  # type: ignore[arg-type]
        authority_scope="contract_testing",
    )
    allowed = contract_testing._promote_completed_generation(
        summaries=(),
        problem=_problem("contract_fake_control"),
        deployment_identity=None,
    )
    assert allowed.reason == "contract_fake_called"
    assert fake.call_count == 1


class _MixedBindingAndDispositionPort:
    """Return one bound candidate and one honest non-binding CGF row."""

    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> _GenerationResult:
        del cycle_index
        problem_ref = gy_content_hash(problem.model_dump(mode="json"))
        candidate = _Candidate(
            candidate_id="candidate_mixed_bound",
            atom=_Atom(
                "candidate_mixed_bound",
                "sha256:" + "8" * 64,
                problem_frame_ref=problem_ref,
            ),
            diversity_key=("grant", "firms", "mixed", "bound"),
        )
        return _GenerationResult(
            status="generated",
            candidates=(candidate,),
            surrogate_rankings=(
                _Ranking(
                    candidate_id=candidate.candidate_id,
                    score=0.9,
                    voi_estimate=0.2,
                ),
            ),
            grounding_dispositions=(
                _GroundingDisposition(
                    proposal_id="gy_n4.bound",
                    candidate_id=candidate.candidate_id,
                    raw_candidate_hash="sha256:" + "9" * 64,
                    disposition="shadow_bound",
                    selected_relation="exact",
                    shadow_atom_content_hash=candidate.atom.content_hash,
                ),
                _GroundingDisposition(
                    proposal_id="gy_n4.unbound",
                    candidate_id=None,
                    raw_candidate_hash="sha256:" + "a" * 64,
                    disposition="novel_cg3",
                    selected_relation="novel-candidate",
                    identified_atom_id=None,
                    cg2_decision="novel_candidate",
                    cg2_reason="cg2_relation_not_bind_eligible",
                    cg3_decision="route_to_acquisition",
                    cg3_reason="cg3_candidate_unbound",
                ),
            ),
            design_problem_ref=problem_ref,
        )


@pytest.mark.asyncio
async def test_disposition_only_n4_result_never_falls_back_to_grammar() -> None:
    """A usable N4 refusal is a cycle candidate denominator, not spec absence."""

    run = await GenerationCycleController(
        generation_port=_DispositionOnlyGenerationPort(),
        value_port=PendingN8ValuePort(),
        promotion_port=_NoPromotionPort(),
        authority_scope="contract_testing",
        repo_root=REPO_ROOT,
    ).run(
        _problem("education_disposition_only"),
        budget_state=_budget(),
        min_cycles=1,
        max_cycles=1,
    )

    cycle = run.cycles[0]
    assert run.candidate_summaries[0].generation_channel == "n4_owner"
    assert cycle.selected_candidate_ref == "gy_n4.education_teaching_method"
    assert cycle.selected_candidate_content_hash == "sha256:" + "7" * 64
    assert cycle.grounding.grounding_source == "cgf_firewall"
    assert cycle.grounding.grounding_disposition == "novel_cg3"
    assert cycle.grounding.acquisition_requirement is not None
    assert cycle.grounding.acquisition_requirement.metadata["source"] == ("cgf_grounding_coverage")
    assert cycle.terminal_kind == "acquisition_required"
    assert cycle.acquisition_routing_report is not None
    assert cycle.acquisition_routing_report.status == "pass"
    assert cycle.terminal_kind != "a_spec_gap"
    assert "grammar_fallback" not in json.dumps(cycle.model_dump(mode="json"))


@pytest.mark.asyncio
async def test_mixed_n4_result_keeps_non_binding_disposition_in_denominator() -> None:
    """The bridge covers every disposition, not only the all-empty case."""

    run = await GenerationCycleController(
        generation_port=_MixedBindingAndDispositionPort(),
        value_port=PendingN8ValuePort(),
        promotion_port=_NoPromotionPort(),
        authority_scope="contract_testing",
        repo_root=REPO_ROOT,
    ).run(
        _problem("mixed_disposition_denominator"),
        budget_state=_budget(),
        min_cycles=1,
        max_cycles=1,
    )

    assert {summary.candidate_id for summary in run.candidate_summaries} == {
        "candidate_mixed_bound",
        "gy_n4.unbound",
    }
    assert {summary.generation_channel for summary in run.candidate_summaries} == {"n4_owner"}
    unbound = next(
        summary for summary in run.candidate_summaries if summary.candidate_id == "gy_n4.unbound"
    )
    assert unbound.content_hash == "sha256:" + "a" * 64
    assert unbound.grounding_disposition == "novel_cg3"


class _FabricatedPromotionPort:
    def __call__(self, *, summaries: Any, problem: DesignProblem) -> PromotionPortObservation:
        del problem
        return PromotionPortObservation(
            status="certified_current_valid",
            certified_candidate_ids=tuple(summary.candidate_id for summary in summaries),
            receipts=tuple(
                _n9_receipt(summary.candidate_id, consumer_promotable=True) for summary in summaries
            ),
        )


class _ShrinkingSimulationPort:
    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
    ) -> SimulationPortObservation:
        del problem, cycle_index
        return SimulationPortObservation(
            candidate_id=str(candidate.candidate_id),
            status="joint_simulated",
            simulation_ref="sha256:" + "6" * 64,
            k_world_ref_before="world_model_record_before",
            k_world_ref_after="world_model_record_after",
        )


def _problem(problem_id: str = "generic_cycle_problem") -> DesignProblem:
    return DesignProblem(
        design_problem_id=problem_id,
        problem_statement="Improve firm survival with grounded support under fiscal constraints.",
        domain="generic_policy",
        nl_provenance=NLProvenance(
            raw_request="Improve firm survival with grounded support.",
            source_surface="test_generation_cycle",
        ),
        authority_profile=AuthorityProfile(
            requester_authority="research_lab",
            requested_authority_level="research",
            mandate="test-only research mandate",
        ),
        jurisdiction_time=JurisdictionTimeSemantics(
            region="UA",
            valid_time="2026",
            as_of="2026-06-29",
            policy_time="2026",
            data_time="2026",
        ),
        objectives=[
            DesignObjective(
                objective_id="firm_survival",
                description="Improve firm survival",
                metric_id="firm_survival",
            )
        ],
        constraints=[
            DesignConstraint(
                constraint_id="shadow_only",
                description="Generated candidates remain shadow until A/N9 certification.",
                hard=True,
                admissibility_basis="request_text",
                source_text="Do not promote generated candidates.",
            )
        ],
        stakeholders=[
            DesignStakeholder(
                stakeholder_id="firms",
                name="Firms",
                role="target_population",
            )
        ],
        outcome_of_interest=OutcomeOfInterest(
            target_variable="firm_survival",
            metric_id="firm_survival",
            estimand="average_treatment_effect",
        ),
        candidate_lever_space=CandidateLeverSpace(
            allowed_operator_kinds=["grant", "tax_relief"],
            candidate_levers=[
                CandidateLever(
                    lever_id="grant",
                    operator_kind="grant",
                    instrument="Targeted grant",
                    target_slot="government_balance",
                )
            ],
        ),
        evidence_acquisition_needs=EvidenceAcquisitionNeeds(
            needs=[
                EvidenceNeed(
                    need_id="supporting_data",
                    question="Which data grounds this effect?",
                    required_for="A-side grounding",
                )
            ]
        ),
    )


def _open_world_summary(candidate_id: str = "open_world_candidate") -> CandidateSummary:
    return CandidateSummary(
        candidate_id=candidate_id,
        content_hash="sha256:" + hashlib.sha256(candidate_id.encode()).hexdigest(),
        cycle_index=0,
        proxy_score=0.2,
        voi_estimate=0.1,
        grounding_status="current_valid",
        grounding_source="cgf_firewall",
        grounding_disposition="shadow_bound",
        grounding_score=0.95,
        current_valid=True,
        value_status="value_ready",
        value_decision_grade="high",
        value_ref="sha256:" + hashlib.sha256(f"{candidate_id}:value".encode()).hexdigest(),
        front="research",
        high_proxy=False,
        low_grounding=False,
    )


class _AppointedTestEpochVerifier:
    """Test-only verifier whose receipt is still checked by the real DV owner."""

    def __init__(self, verifier_provenance_ref: core_contracts.ArtifactRef) -> None:
        self.verifier_provenance_ref = verifier_provenance_ref
        self.receipt: core_contracts.EpochTransitionVerificationReceipt | None = None

    def verify(self, **_kwargs: Any) -> core_contracts.EpochTransitionVerificationReceipt:
        assert self.receipt is not None
        return self.receipt


def _positive_epoch_admitted_batch(
    *,
    runtime: PromotionRuntime,
    problem: DesignProblem,
    summaries: tuple[CandidateSummary, ...],
) -> core_contracts.PersistedPreN9AdmittedCandidateBatch:
    """Test-only owner appointment; production remains policy-admission missing."""

    prepared = runtime._prepare_completed_generation(problem=problem, summaries=summaries)
    assert hasattr(prepared, "candidate_denominator")
    aggregate = prepared.contexts.aggregate_context
    verifier_provenance_ref = runtime.store.put_json(
        {"verifier": "appointed-test-epoch-transition-verifier"},
        ArtifactWriteOptions(
            kind="chronology.epoch_transition_verifier",
            media_type="application/json",
        ),
    )
    verifier = _AppointedTestEpochVerifier(verifier_provenance_ref)
    decision_validity = DecisionValidityService(
        runtime.store,
        epoch_transition_verifier=verifier,
    )
    admissions = []
    for ordinal, bound in enumerate(prepared.contexts.ordered_bound_members):
        subject = runtime.epoch_subject_authority.persist_for_n9(
            bound_member_ref=bound.bound_member_ref
        )
        candidate = aggregate.statement.ordered_candidate_contexts[ordinal]
        dependency_key = f"epoch::test-owner::{candidate.candidate.candidate_id}"
        envelope = core_contracts.DecisionValidityEnvelope(
            decision_lineage_key=f"test-epoch-lineage::{candidate.candidate.candidate_id}",
            policy_fingerprint=f"test-epoch-policy::{candidate.candidate.candidate_id}",
            knowledge_basis=core_contracts.DecisionBasisSection(
                dependencies=[
                    core_contracts.DecisionDependencyRef(
                        kind=core_contracts.DecisionDependencyKind.SEMANTIC_EPOCH,
                        key=dependency_key,
                        artifact_id=str(candidate.epoch_query.query_artifact_ref.artifact_id),
                    )
                ]
            ),
        )
        baseline = core_contracts.DecisionValidityEvaluation(
            decision_lineage_key=envelope.decision_lineage_key,
            status=core_contracts.DecisionValidityStatus.ACTIVE,
            dependency_keys=envelope.dependency_keys(),
        )
        packet_ref = runtime.store.put_json(
            {
                "schema_version": "3.4",
                "decision_validity_envelope": envelope.model_dump(mode="json"),
                "decision_validity_baseline": baseline.model_dump(mode="json"),
            },
            ArtifactWriteOptions(
                kind="scientist.decision_packet",
                media_type="application/json",
            ),
        )
        packet_id = str(packet_ref.artifact_id)
        decision_validity.register_decision_packet(
            packet_ref=packet_id,
            envelope=envelope,
            baseline=baseline,
        )
        transition_ref = runtime.store.put_json(
            {"candidate_id": candidate.candidate.candidate_id, "ordinal": ordinal},
            ArtifactWriteOptions(
                kind="chronology.epoch_transition",
                media_type="application/json",
            ),
        )
        transition_bytes = runtime.store.get_bytes(transition_ref.artifact_id)
        _, dependency_denominator_ref = decision_validity._resolve_epoch_target_denominator(
            dependency_keys=(dependency_key,)
        )
        adjudication_denominator_ref = gy_content_hash(
            {"candidate": candidate.candidate.candidate_id, "kind": "adjudication"}
        )
        verifier.receipt = core_contracts.EpochTransitionVerificationReceipt(
            transition_artifact_ref=transition_ref,
            transition_content_hash="sha256:" + hashlib.sha256(transition_bytes).hexdigest(),
            requested_query_context_ref=(candidate.epoch_query.native_requested_query_context_ref),
            authority_purpose="decision_validity_epoch_transition",
            verifier_provenance_ref=verifier_provenance_ref,
            dependency_keys=(dependency_key,),
            dependency_denominator_ref=dependency_denominator_ref,
            adjudication_denominator_ref=adjudication_denominator_ref,
            targets=(
                core_contracts.EpochValidityBatchTarget(
                    packet_ref=packet_id,
                    decision_lineage_key=envelope.decision_lineage_key,
                    dependency_key=dependency_key,
                    status=core_contracts.DecisionValidityStatus.STALE,
                    reason="test_epoch_advanced",
                ),
            ),
            predicate_class="independently_reconciled",
        )
        completed = decision_validity.admit_epoch_validity_batch(
            transition_artifact_ref=transition_ref,
            requested_query_context_ref=(candidate.epoch_query.native_requested_query_context_ref),
        )
        completed_evidence = decision_validity.resolve_completed_epoch_batch_evidence_by_id(
            batch_id=completed.batch_id
        )
        gate = core_contracts.EpochValidityGateReceipt(
            status="batch_completed",
            subject_ref=subject.subject_ref,
            subject_content_hash=subject.subject_content_hash,
            current_decision_packet_ref=None,
            packet_epoch_refs=(),
            current_epoch_head_refs=(candidate.epoch_query.native_requested_query_context_ref,),
            dependency_denominator_ref=completed.dependency_denominator_ref,
            adjudication_denominator_ref=completed.adjudication_denominator_ref,
            prior_completed_binding_ref=None,
            completed_batch_receipt_ref=completed_evidence.batch_receipt_ref,
            requested_query_context_ref=candidate.epoch_query.native_requested_query_context_ref,
            failure_codes=(),
        )
        gate_ref, gate_hash, _ = epoch_cascade_module._persist_model(
            store=runtime.store,
            value=gate,
            profile_record="epoch_validity_gate_receipt",
        )
        occurrence = runtime.context_repository.resolve_occurrence(
            occurrence_ref=bound.statement.candidate_occurrence_ref
        )
        admissions.append(
            core_contracts.PreN9AdmittedCandidate(
                aggregate_context_ref=aggregate.context_ref,
                aggregate_context_content_hash=aggregate.semantic_hash,
                bound_member_ref=bound.bound_member_ref,
                bound_member_content_hash=bound.bound_member_content_hash,
                candidate_occurrence_ref=bound.statement.candidate_occurrence_ref,
                candidate_occurrence_content_hash=core_contracts.c4_semantic_digest(
                    "candidate_occurrence", occurrence
                ),
                subject_ref=subject.subject_ref,
                subject_content_hash=subject.subject_content_hash,
                gate_evidence_ref=gate_ref,
                gate_evidence_content_hash=gate_hash,
            )
        )
    runtime.epoch_n9_evidence_resolver = (
        epoch_cascade_module.ArtifactEpochValidityN9EvidenceResolver(
            store=runtime.store,
            contexts=runtime.context_repository,
            verifier_provenance_ref=runtime.verifier_provenance_ref,
            completed_batches=decision_validity,
        )
    )
    return epoch_cascade_module.seal_pre_n9_admitted_candidate_batch(
        store=runtime.store,
        denominator=prepared.candidate_denominator,
        contexts=prepared.contexts,
        admissions=admissions,
    )


def test_core_generation_controller_cannot_bypass_epoch_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real post-loop composition reaches DV and never calls N9 on no policy."""

    class _ForbiddenN9:
        called = False

        def __call__(self, **_kwargs: Any) -> PromotionPortObservation:
            self.called = True
            raise AssertionError("N9 must not run without an admitted epoch policy")

    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    qualify_calls = 0
    real_qualify = runtime.semantic_epoch_service.qualify_chronology_query

    def _counted_qualify(**kwargs: Any) -> Any:
        nonlocal qualify_calls
        qualify_calls += 1
        return real_qualify(**kwargs)

    monkeypatch.setattr(
        runtime.semantic_epoch_service,
        "qualify_chronology_query",
        _counted_qualify,
    )
    n9 = _ForbiddenN9()
    controller = GenerationCycleController(
        promotion_runtime=runtime,
        promotion_port=n9,
        authority_scope="contract_testing",
    )

    result = controller._promote_completed_generation(
        summaries=(_open_world_summary(),),
        problem=_problem("epoch_gate_negative_path"),
    )

    assert result.status == "not_promoted"
    assert result.reason == "epoch_validity_refused:policy_admission_missing"
    assert result.receipts == ()
    assert result.certified_candidate_ids == ()
    assert len(getattr(result, "pre_n9_open_world_gates", ())) == 1
    gate_observation = result.pre_n9_open_world_gates[0]
    assert gate_observation.ordinal == 0
    assert gate_observation.gate_payload["status"] == "not_established"
    assert gate_observation.gate_payload["limitation_code"] == ("deployment_scope_not_established")
    # One invocation persists the owner query and a second, independent
    # invocation requalifies it at the pre-N9 gate.  Keeping only the stored
    # failure-code markers therefore makes this falsifier red.
    assert qualify_calls == 2
    assert n9.called is False


def test_empty_pre_n9_open_world_observation_does_not_change_existing_wire_shape() -> None:
    """The new replay carrier must not alter unrelated promotion-port payloads."""

    payload = PromotionPortObservation().model_dump(mode="json")

    assert "pre_n9_open_world_gates" not in payload


def test_gate_derives_query_context_from_owner_context_not_controller(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stored failure-code markers cannot replace a fresh service result."""

    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    problem = _problem("gate_owner_query_context")
    prepared = runtime._prepare_completed_generation(
        problem=problem,
        summaries=(_open_world_summary("gate_owner_query_context_candidate"),),
    )
    assert hasattr(prepared, "contexts")
    bound = prepared.contexts.ordered_bound_members[0]
    subject = runtime.epoch_subject_authority.persist_for_n9(
        bound_member_ref=bound.bound_member_ref
    )
    epoch_query = prepared.contexts.aggregate_context.statement.ordered_candidate_contexts[
        0
    ].epoch_query
    statement = epoch_cascade_module._read_model(
        store=runtime.store,
        ref=epoch_query.query_artifact_ref,
        model=epoch_cascade_module.PersistedEpochPromotionQueryStatement,
        profile_record="epoch_query_evidence",
    )
    assert isinstance(
        statement,
        epoch_cascade_module.PersistedEpochPromotionQueryStatement,
    )
    stored = statement.qualification_result
    substituted_query = stored.query.model_copy(
        update={
            "requested_query_context_ref": "sha256:"
            + hashlib.sha256(b"controller-substitution").hexdigest()
        }
    )
    monkeypatch.setattr(
        runtime.semantic_epoch_service,
        "qualify_chronology_query",
        lambda **_kwargs: stored.model_copy(update={"query": substituted_query}),
    )

    result = runtime.epoch_validity_gate.reconcile_before_n9(subject_ref=subject.subject_ref)

    assert isinstance(result, core_contracts.EpochValidityGateNonReceipt)
    assert result.code == "epoch_validity_subject_unresolved"
    assert epoch_query.qualification_failure_codes == ("policy_admission_missing",)


def test_first_decision_uses_candidate_subject_without_fabricated_prior_packet(
    tmp_path: Path,
) -> None:
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    prepared = runtime._prepare_completed_generation(
        problem=_problem("epoch_gate_first_decision"),
        summaries=(_open_world_summary("first_decision_candidate"),),
    )
    assert hasattr(prepared, "contexts")
    bound = prepared.contexts.ordered_bound_members[0]
    persisted = runtime.epoch_subject_authority.persist_for_n9(
        bound_member_ref=bound.bound_member_ref
    )
    payload = canon.from_canonical_bytes(runtime.store.get_bytes(persisted.subject_ref.artifact_id))
    subject = core_contracts.PreN9EpochValiditySubjectStatement.model_validate(payload)

    assert subject.current_decision_packet_ref is None
    assert subject.packet_epoch_refs == ()
    assert subject.bound_member_ref == bound.bound_member_ref


def test_owr_and_epoch_gate_bind_identical_owner_context_ref(tmp_path: Path) -> None:
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    problem = _problem("identical_owner_context")
    admitted = _positive_epoch_admitted_batch(
        runtime=runtime,
        problem=problem,
        summaries=(_open_world_summary("identical_context_candidate"),),
    )
    row = admitted.ordered_admissions[0]
    aggregate = runtime.context_repository.resolve_verified(context_ref=row.aggregate_context_ref)
    assert hasattr(aggregate, "statement")
    epoch = runtime.epoch_n9_evidence_resolver.resolve_verified(
        admission=row,
        expected_design_problem_ref=aggregate.statement.design_problem_binding_ref,
    )
    open_world = runtime.open_world_authority.prepare_verified_projection(
        bound_member_ref=row.bound_member_ref
    )

    assert isinstance(epoch, core_contracts.EpochValidityN9Projection)
    assert isinstance(open_world, VerifiedOpenWorldRiskVector)
    assert epoch.owner_query_context_ref == open_world.aggregate_context_ref
    assert (
        epoch.owner_query_context_content_hash == open_world.vector.aggregate_context_content_hash
    )


def test_canonical_n9_resolves_sealed_epoch_gate_evidence(tmp_path: Path) -> None:
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    problem = _problem("sealed_epoch_gate")
    admitted = _positive_epoch_admitted_batch(
        runtime=runtime,
        problem=problem,
        summaries=(_open_world_summary("sealed_epoch_candidate"),),
    )
    row = admitted.ordered_admissions[0]
    aggregate = runtime.context_repository.resolve_verified(context_ref=row.aggregate_context_ref)

    projection = runtime.epoch_n9_evidence_resolver.resolve_verified(
        admission=row,
        expected_design_problem_ref=aggregate.statement.design_problem_binding_ref,
    )

    assert isinstance(projection, core_contracts.EpochValidityN9Projection)
    assert projection.subject_ref == row.subject_ref
    assert projection.gate_receipt_ref == row.gate_evidence_ref
    assert projection.predicate_class == "independently_reconciled"


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "reordered"])
def test_pre_n9_admission_batch_is_an_exact_ordered_denominator(
    tmp_path: Path,
    mutation: str,
) -> None:
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    admitted = _positive_epoch_admitted_batch(
        runtime=runtime,
        problem=_problem(f"admission_denominator_{mutation}"),
        summaries=(
            _open_world_summary(f"admission_{mutation}_a"),
            _open_world_summary(f"admission_{mutation}_b"),
        ),
    )
    denominator_statement = runtime.context_repository.resolve_denominator(
        denominator_ref=admitted.candidate_denominator_ref
    )
    denominator = epoch_cascade_module.PersistedPromotionCandidateDenominator(
        denominator_ref=admitted.candidate_denominator_ref,
        denominator_content_hash=admitted.candidate_denominator_content_hash,
        statement=denominator_statement,
    )
    aggregate = runtime.context_repository.resolve_verified(
        context_ref=admitted.aggregate_context_ref
    )
    assert hasattr(aggregate, "statement")
    contexts = epoch_cascade_module.PersistedPromotionContextBatch(
        aggregate_context=aggregate,
        ordered_bound_members=tuple(
            runtime.context_repository.resolve_bound_member(bound_member_ref=row.bound_member_ref)
            for row in admitted.ordered_admissions
        ),
    )
    rows = admitted.ordered_admissions
    changed = {
        "missing": rows[:-1],
        "duplicate": (rows[0], rows[0]),
        "reordered": tuple(reversed(rows)),
    }[mutation]

    with pytest.raises(ValueError, match="epoch_validity_admission_denominator_mismatch"):
        epoch_cascade_module.seal_pre_n9_admitted_candidate_batch(
            store=runtime.store,
            denominator=denominator,
            contexts=contexts,
            admissions=changed,
        )


def test_pre_n9_batch_rejects_shaped_denominator_hash(tmp_path: Path) -> None:
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    problem = _problem("shaped_denominator_hash")
    admitted = _positive_epoch_admitted_batch(
        runtime=runtime,
        problem=problem,
        summaries=(_open_world_summary("shaped_denominator_hash_candidate"),),
    )
    changed = admitted.model_copy(
        update={"candidate_denominator_content_hash": "sha256:" + "f" * 64}
    )
    changed = changed.model_copy(
        update={
            "batch_content_hash": core_contracts.c4_semantic_digest(
                "pre_n9_admitted_candidate_batch", changed
            )
        }
    )

    with pytest.raises(
        ValueError,
        match="pre_n9_admitted_batch_denominator_binding_mismatch",
    ):
        CanonicalN9PromotionPort(
            promotion_runtime=runtime,
            epoch_n9_evidence_resolver=runtime.epoch_n9_evidence_resolver,
            repo_root=REPO_ROOT,
        )(
            admitted_batch=changed,
            problem=problem,
            deployment_identity=_canonical_loaded_deployment_identity(),
        )


def test_positive_epoch_gate_cannot_carry_failure_codes(tmp_path: Path) -> None:
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    admitted = _positive_epoch_admitted_batch(
        runtime=runtime,
        problem=_problem("positive_gate_failure_code"),
        summaries=(_open_world_summary("positive_gate_failure_code_candidate"),),
    )
    row = admitted.ordered_admissions[0]
    gate = epoch_cascade_module._read_model(
        store=runtime.store,
        ref=row.gate_evidence_ref,
        model=core_contracts.EpochValidityGateReceipt,
        profile_record="epoch_validity_gate_receipt",
    )
    payload = gate.model_dump(mode="json")
    payload["failure_codes"] = ["caller_shaped_positive"]

    with pytest.raises(ValueError, match="epoch_validity_positive_status_has_failure_codes"):
        core_contracts.EpochValidityGateReceipt.model_validate(payload)


def test_completed_epoch_receipt_bytes_are_reloaded_before_n9(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    problem = _problem("tampered_completed_epoch_receipt")
    admitted = _positive_epoch_admitted_batch(
        runtime=runtime,
        problem=problem,
        summaries=(_open_world_summary("tampered_completed_epoch_candidate"),),
    )
    row = admitted.ordered_admissions[0]
    aggregate = runtime.context_repository.resolve_verified(context_ref=row.aggregate_context_ref)
    gate = epoch_cascade_module._read_model(
        store=runtime.store,
        ref=row.gate_evidence_ref,
        model=core_contracts.EpochValidityGateReceipt,
        profile_record="epoch_validity_gate_receipt",
    )
    assert gate.completed_batch_receipt_ref is not None
    completed_id = gate.completed_batch_receipt_ref.artifact_id
    real_get_bytes = runtime.store.get_bytes

    def _tamper_completed_receipt(artifact_id):
        if artifact_id == completed_id:
            return b'{"forged":"completed-receipt"}'
        return real_get_bytes(artifact_id)

    monkeypatch.setattr(runtime.store, "get_bytes", _tamper_completed_receipt)
    result = runtime.epoch_n9_evidence_resolver.resolve_verified(
        admission=row,
        expected_design_problem_ref=aggregate.statement.design_problem_binding_ref,
    )

    assert isinstance(result, core_contracts.EpochValidityGateNonReceipt)
    assert result.code == "epoch_validity_gate_evidence_unresolved"


def test_completed_epoch_transition_bytes_are_reloaded_before_n9(
    tmp_path: Path,
) -> None:
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    problem = _problem("tampered_completed_epoch_transition")
    admitted = _positive_epoch_admitted_batch(
        runtime=runtime,
        problem=problem,
        summaries=(_open_world_summary("tampered_completed_transition_candidate"),),
    )
    row = admitted.ordered_admissions[0]
    aggregate = runtime.context_repository.resolve_verified(context_ref=row.aggregate_context_ref)
    gate = epoch_cascade_module._read_model(
        store=runtime.store,
        ref=row.gate_evidence_ref,
        model=core_contracts.EpochValidityGateReceipt,
        profile_record="epoch_validity_gate_receipt",
    )
    assert gate.completed_batch_receipt_ref is not None
    completed_owner = runtime.epoch_n9_evidence_resolver._completed_batches
    assert completed_owner is not None
    completed = completed_owner.resolve_completed_epoch_batch_evidence(
        batch_receipt_ref=gate.completed_batch_receipt_ref
    )
    transition_blob, _ = runtime.store._paths(completed.receipt.transition_artifact_ref.artifact_id)
    transition_blob.write_bytes(b'{"forged":"transition"}')

    result = runtime.epoch_n9_evidence_resolver.resolve_verified(
        admission=row,
        expected_design_problem_ref=aggregate.statement.design_problem_binding_ref,
    )

    assert isinstance(result, core_contracts.EpochValidityGateNonReceipt)
    assert result.code == "epoch_validity_gate_evidence_unresolved"


def test_missing_or_mutated_owner_context_freezes_n9(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        promotion_sequence_module,
        "_legacy_policy_promotion_callers",
        lambda repo_root: (),
    )
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "owner-cas"))
    foreign_runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "foreign-cas"))
    problem = _problem("authentic_second_owner_context")
    summary = _open_world_summary("authentic_second_context_candidate")
    admitted = _positive_epoch_admitted_batch(
        runtime=runtime,
        problem=problem,
        summaries=(summary,),
    )
    foreign = _positive_epoch_admitted_batch(
        runtime=foreign_runtime,
        problem=problem,
        summaries=(summary, _open_world_summary("foreign_denominator_extra_candidate")),
    )
    foreign_export = tmp_path / "foreign-owner-context"
    foreign_runtime.store.export_subgraph(
        foreign_runtime.store.iter_artifact_ids(),
        foreign_export,
        compress=False,
    )
    imported = runtime.store.import_subgraph(foreign_export, verify_integrity=True)
    assert imported.imported_artifacts > 0
    foreign_first = foreign.ordered_admissions[0]
    assert runtime.store.verify(foreign_first.aggregate_context_ref.artifact_id).ok
    assert runtime.store.verify(foreign_first.bound_member_ref.artifact_id).ok
    foreign_aggregate = runtime.context_repository.resolve_verified(
        context_ref=foreign_first.aggregate_context_ref
    )
    assert hasattr(foreign_aggregate, "statement")
    assert foreign_aggregate.semantic_hash == foreign_first.aggregate_context_content_hash
    foreign_member = runtime.context_repository.resolve_bound_member(
        bound_member_ref=foreign_first.bound_member_ref
    )
    assert foreign_member.bound_member_content_hash == foreign_first.bound_member_content_hash
    first = admitted.ordered_admissions[0].model_copy(
        update={
            "aggregate_context_ref": foreign_first.aggregate_context_ref,
            "aggregate_context_content_hash": foreign_first.aggregate_context_content_hash,
            "bound_member_ref": foreign_first.bound_member_ref,
            "bound_member_content_hash": foreign_first.bound_member_content_hash,
        }
    )
    changed = admitted.model_copy(update={"ordered_admissions": (first,)})
    changed = changed.model_copy(
        update={
            "batch_content_hash": core_contracts.c4_semantic_digest(
                "pre_n9_admitted_candidate_batch",
                changed,
            )
        }
    )

    result = CanonicalN9PromotionPort(
        promotion_runtime=runtime,
        epoch_n9_evidence_resolver=runtime.epoch_n9_evidence_resolver,
        repo_root=REPO_ROOT,
    )(
        admitted_batch=changed,
        problem=problem,
        deployment_identity=_canonical_loaded_deployment_identity(),
    )

    assert result.status == "not_promoted"
    assert result.reason == "epoch_validity_refused:epoch_validity_gate_evidence_unresolved"


def test_old_packet_after_prior_head_advance_requires_validity_batch(
    tmp_path: Path,
) -> None:
    """Absent owner authority can never relabel an authentic old subject current."""

    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    prepared = runtime._prepare_completed_generation(
        problem=_problem("authentic_old_subject"),
        summaries=(_open_world_summary("authentic_old_candidate"),),
    )
    bound = prepared.contexts.ordered_bound_members[0]
    persisted = runtime.epoch_subject_authority.persist_for_n9(
        bound_member_ref=bound.bound_member_ref
    )
    subject = epoch_cascade_module._read_model(
        store=runtime.store,
        ref=persisted.subject_ref,
        model=core_contracts.PreN9EpochValiditySubjectStatement,
        profile_record="pre_n9_epoch_subject",
    )
    old_subject = subject.model_copy(
        update={
            "current_decision_packet_ref": runtime.verifier_provenance_ref,
            "packet_epoch_refs": ("sha256:" + hashlib.sha256(b"authentic-old-epoch").hexdigest(),),
        }
    )
    old_ref, _, _ = epoch_cascade_module._persist_model(
        store=runtime.store,
        value=old_subject,
        profile_record="pre_n9_epoch_subject",
    )

    result = runtime.epoch_validity_gate.reconcile_before_n9(subject_ref=old_ref)

    assert isinstance(result, core_contracts.EpochValidityGateNonReceipt)
    assert result.code == "policy_admission_missing"


def test_post_n9_packet_binds_exact_subject_and_gate_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The emitted N9 receipt binds the exact owner admission handles."""

    monkeypatch.setattr(
        promotion_sequence_module,
        "_legacy_policy_promotion_callers",
        lambda repo_root: (),
    )
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    problem = _problem("post_n9_exact_epoch_binding")
    admitted = _positive_epoch_admitted_batch(
        runtime=runtime,
        problem=problem,
        summaries=(_open_world_summary("post_n9_exact_epoch_candidate"),),
    )
    admission = admitted.ordered_admissions[0]
    observation = CanonicalN9PromotionPort(
        promotion_runtime=runtime,
        epoch_n9_evidence_resolver=runtime.epoch_n9_evidence_resolver,
        repo_root=REPO_ROOT,
    )(
        admitted_batch=admitted,
        problem=problem,
        deployment_identity=_canonical_loaded_deployment_identity(),
    )
    assert observation.receipts
    receipt = CanonicalPromotionReceipt.model_validate(observation.receipts[0])
    projection = receipt.owner_projection.epoch_validity_projection

    assert projection is not None
    assert (
        projection.owner_query_context_ref,
        projection.owner_query_context_content_hash,
        projection.bound_member_ref,
        projection.bound_member_content_hash,
        projection.candidate_occurrence_ref,
        projection.candidate_occurrence_content_hash,
        projection.subject_ref,
        projection.subject_content_hash,
        projection.gate_receipt_ref,
        projection.gate_receipt_content_hash,
    ) == (
        admission.aggregate_context_ref,
        admission.aggregate_context_content_hash,
        admission.bound_member_ref,
        admission.bound_member_content_hash,
        admission.candidate_occurrence_ref,
        admission.candidate_occurrence_content_hash,
        admission.subject_ref,
        admission.subject_content_hash,
        admission.gate_evidence_ref,
        admission.gate_evidence_content_hash,
    )
    subject = epoch_cascade_module._read_model(
        store=runtime.store,
        ref=projection.subject_ref,
        model=core_contracts.PreN9EpochValiditySubjectStatement,
        profile_record="pre_n9_epoch_subject",
    )
    gate = epoch_cascade_module._read_model(
        store=runtime.store,
        ref=projection.gate_receipt_ref,
        model=core_contracts.EpochValidityGateReceipt,
        profile_record="epoch_validity_gate_receipt",
    )
    assert gate.subject_ref == projection.subject_ref
    assert gate.subject_content_hash == projection.subject_content_hash
    assert gate.completed_batch_receipt_ref is not None
    assert subject.owner_query_context_ref == projection.owner_query_context_ref
    resolved = runtime.epoch_n9_evidence_resolver.resolve_projection_verified(
        projection=projection,
        expected_problem_content_hash=(
            receipt.owner_projection.design_problem_binding.problem_content_hash
        ),
    )
    assert resolved == projection

    foreign_runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "foreign-cas"))
    second = _positive_epoch_admitted_batch(
        runtime=foreign_runtime,
        problem=problem,
        summaries=(_open_world_summary("post_n9_authentic_substitute"),),
    ).ordered_admissions[0]
    foreign_export = tmp_path / "authentic-substitute"
    foreign_runtime.store.export_subgraph(
        foreign_runtime.store.iter_artifact_ids(),
        foreign_export,
        compress=False,
    )
    imported = runtime.store.import_subgraph(foreign_export, verify_integrity=True)
    assert imported.imported_artifacts > 0
    assert runtime.store.verify(second.subject_ref.artifact_id).ok
    assert runtime.store.verify(second.gate_evidence_ref.artifact_id).ok
    substituted = projection.model_copy(
        update={
            "subject_ref": second.subject_ref,
            "subject_content_hash": second.subject_content_hash,
            "gate_receipt_ref": second.gate_evidence_ref,
            "gate_receipt_content_hash": second.gate_evidence_content_hash,
        }
    )
    rejected = runtime.epoch_n9_evidence_resolver.resolve_projection_verified(
        projection=substituted,
        expected_problem_content_hash=(
            receipt.owner_projection.design_problem_binding.problem_content_hash
        ),
    )
    assert isinstance(rejected, core_contracts.EpochValidityGateNonReceipt)
    assert rejected.code == "epoch_validity_gate_evidence_unresolved"


def test_offline_epoch_projection_types_corrupt_completed_owner_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, _, _, receipt = _run_open_world_n9_case(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )
    projection = receipt.owner_projection.epoch_validity_projection
    assert projection is not None
    completed_owner = runtime.epoch_n9_evidence_resolver._completed_batches
    assert completed_owner is not None

    def corrupt_completed_owner_state(**_kwargs):
        raise RuntimeError("decision_validity_owner_state_corrupt")

    monkeypatch.setattr(
        completed_owner,
        "resolve_completed_epoch_batch_evidence",
        corrupt_completed_owner_state,
    )
    resolved = runtime.epoch_n9_evidence_resolver.resolve_projection_verified(
        projection=projection,
        expected_problem_content_hash=(
            receipt.owner_projection.design_problem_binding.problem_content_hash
        ),
    )

    assert isinstance(resolved, core_contracts.EpochValidityGateNonReceipt)
    assert resolved.code == "epoch_validity_gate_evidence_unresolved"


def _domain_problem(
    *,
    domain: str,
    region: str,
    valid_time: str,
    as_of: str,
    outcome: str,
    stakeholder_id: str,
) -> DesignProblem:
    """Build a domain-shaped problem without changing the boundary owner."""

    return _problem(f"{domain}_boundary_problem").model_copy(
        update={
            "domain": domain,
            "jurisdiction_time": JurisdictionTimeSemantics(
                region=region,
                valid_time=valid_time,
                as_of=as_of,
                policy_time=valid_time,
                data_time=valid_time,
            ),
            "stakeholders": [
                DesignStakeholder(
                    stakeholder_id=stakeholder_id,
                    name=stakeholder_id.replace("_", " ").title(),
                    role="affected_population",
                )
            ],
            "outcome_of_interest": OutcomeOfInterest(
                target_variable=outcome,
                metric_id=outcome,
                estimand="average_treatment_effect",
            ),
        }
    )


def _lane0_registry(*, domain: str, source_id: str) -> SubstrateRegistry:
    """Build one content-addressed registry with domain-shaped vocabulary."""

    registration = SubstrateRegistration(
        source_id=source_id,
        family_id=f"{domain}_causal_priors",
        layer=SubstrateLayer.L2,
        coverage=SubstrateCoverage(
            coverage_score=0.74,
            coverage_kind="lane0.causal_claim_coverage",
            coverage_rule_ref=f"lane0://{domain}/coverage",
            observation_count=7,
            metric_binding_count=3,
        ),
        trust_tier=SubstrateTrustTier(
            tier="derived_proxy",
            trust_cap=0.5,
            trust_multiplier=0.6,
            min_coverage=0.0,
            max_coverage=1.0,
            authority_ref=f"lane0://{domain}/trust",
        ),
        identification_mode="causal_prior_candidate",
        schema_regime=SubstrateSchemaRegime(
            schema_regime_id=f"{domain}_schema_v1",
            authority_ref=f"lane0://{domain}/schema",
            source_version="1",
        ),
        data_version=f"{domain}-data-v1",
        snapshot_id=f"{domain}-snapshot-v1",
        source_snapshot_id=f"{domain}-snapshot-v1",
        provenance_refs=(f"lane0://{domain}/causal-claims",),
        authority_refs=(f"lane0://{domain}/registry-owner",),
    )
    return build_substrate_registry(
        (build_substrate_registry_entry(registration),),
        producer_ref="tests.unit.runtime.quality.test_generation_cycle",
        source_catalog_refs=registration.authority_refs,
    )


def _lane0_cycle_context(
    *,
    runtime_hints: dict[str, Any] | None = None,
) -> tuple[DesignProblem, CycleSubstrateContext]:
    """Build one unseen-shape context through the canonical boundary owner."""

    problem = _domain_problem(
        domain="water_quality",
        region="dnieper_basin",
        valid_time="2021/2024",
        as_of="2026-07-12",
        outcome="nitrate_load",
        stakeholder_id="watershed_communities",
    )
    if runtime_hints is not None:
        problem = problem.model_copy(update={"runtime_hints": runtime_hints})
    registry = _lane0_registry(
        domain="water_quality",
        source_id="l2_watershed_graph:causal_edges.duckdb",
    )
    selected_hash = registry.entries[0].entry_content_hash
    world = _build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=problem,
        outcome="nitrate_load",
        policy_slot_ids=("nitrate_load",),
        substrate_registry=registry,
        selected_registry_entry_hashes=(selected_hash,),
    )
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    substrate_input_hash = gy_content_hash(
        {"domain": problem.domain, "registry": registry.content_hash}
    )
    binding_hash = cycle_substrate_context_binding_hash(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_input_content_hash=substrate_input_hash,
        substrate_registry_content_hash=registry.content_hash,
        world_model_record_id=world.world_model_record_id,
        world_model_record_content_hash=world.content_hash,
        world_model_record_authority_status=world.authority_status,
        selected_registry_entry_hashes=(selected_hash,),
    )
    candidate = CandidateLeverEvidence(
        lever_id="riparian_buffer_width",
        instrument="water.riparian_buffer_width",
        target_concept="water.nitrate_load",
        status="candidate_unbound",
        entry_content_hash=gy_content_hash(
            {"lever": "riparian_buffer_width", "domain": "water_quality"}
        ),
        substrate_input_content_hash=substrate_input_hash,
        selected_registry_entry_hash=selected_hash,
        context_binding_hash=binding_hash,
        source_refs=("lane0://water-quality/lever",),
    )
    context = build_cycle_substrate_context(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_registry=registry,
        selected_registry_entry_hashes=(selected_hash,),
        world_model_record=world,
        intervention_substrate=None,
        candidate_levers=(candidate,),
        transport_context=None,
        source_pack_content_hash=gy_content_hash("water-quality-pack"),
        substrate_input_content_hash=substrate_input_hash,
    )
    return problem, context


def _candidate_unbound_refusal(
    context: CycleSubstrateContext,
) -> InterventionLeverRefusal:
    """Bind one candidate-only lever refusal to the exact test context."""

    candidate = context.candidate_levers[0]
    payload = {
        "schema_version": "policyos.runtime.intervention_substrate_lift.v2",
        "status": "candidate_unbound",
        "operator_kind": candidate.lever_id,
        "instrument": candidate.instrument,
        "lever_id": candidate.lever_id,
        "reason_code": "knob_operator_unresolved",
        "candidate_entry_content_hash": candidate.entry_content_hash,
        "selected_registry_entry_hash": candidate.selected_registry_entry_hash,
        "substrate_input_content_hash": candidate.substrate_input_content_hash,
        "context_binding_hash": candidate.context_binding_hash,
        "substrate_registry_content_hash": context.substrate_registry_content_hash,
        "world_model_record_content_hash": context.world_model_record_content_hash,
        "source_refs": candidate.source_refs,
    }
    return InterventionLeverRefusal.model_validate(
        {**payload, "content_hash": gy_content_hash(payload)}
    )


def test_disposition_projection_preserves_verified_candidate_unbound_resolution() -> None:
    """N6 keeps owner-verified world identity without inventing an intervention atom."""

    _problem_value, context = _lane0_cycle_context()
    refusal = _candidate_unbound_refusal(context)
    raw_candidate_hash = gy_content_hash({"candidate": "riparian-buffer"})
    disposition = SimpleNamespace(
        candidate_id=None,
        proposal_id="candidate_unbound_riparian_buffer",
        raw_candidate_hash=raw_candidate_hash,
        disposition="unknown_blocked",
        lever_resolution=refusal,
    )

    projected = _disposition_candidates(
        SimpleNamespace(grounding_dispositions=(disposition,)),
        existing_candidates=(),
    )

    assert len(projected) == 1
    assert projected[0].lever_resolution == refusal
    assert not hasattr(projected[0], "atom")


def test_joint_port_uses_verified_candidate_unbound_resolution_for_context_wmr() -> None:
    """N5 may carry the context WMR while the intervention remains explicitly unbound."""

    problem, context = _lane0_cycle_context()
    candidate = SimpleNamespace(
        candidate_id="candidate_unbound_riparian_buffer",
        status="candidate_unbound",
        lever_resolution=_candidate_unbound_refusal(context),
    )

    observation = JointSimulationPort(
        repo_root=REPO_ROOT,
        cycle_substrate_context=context,
    )(candidate=candidate, problem=problem, cycle_index=0)

    assert observation.status == "simulation_pending_n5"
    assert observation.world_model_record is context.world_model_record
    assert observation.diagnostics["world_model_source"] == "cycle_substrate_context"
    assert "world_identity_unresolved" not in observation.authority_blockers
    assert not hasattr(candidate, "atom")


def test_joint_port_rejects_candidate_unbound_resolution_from_another_context() -> None:
    """A valid refusal from another problem cannot act as shaped world identity."""

    problem, context = _lane0_cycle_context()
    _other_problem, other_context = _lane0_cycle_context(runtime_hints={"probe": "another-context"})
    candidate = SimpleNamespace(
        candidate_id="candidate_unbound_cross_context",
        status="candidate_unbound",
        lever_resolution=_candidate_unbound_refusal(other_context),
    )

    observation = JointSimulationPort(
        repo_root=REPO_ROOT,
        cycle_substrate_context=context,
    )(candidate=candidate, problem=problem, cycle_index=0)

    assert observation.status == "simulation_blocked"
    assert "world_identity_unresolved" in observation.authority_blockers
    assert observation.diagnostics["world_model_error_code"] == "world_identity_unresolved"
    assert observation.world_model_record is None


def test_joint_port_missing_candidate_unbound_proof_does_not_inherit_context_wmr() -> None:
    """A candidate status marker cannot substitute for its context-bound refusal."""

    problem, context = _lane0_cycle_context()
    candidate = SimpleNamespace(
        candidate_id="candidate_unbound_without_refusal",
        status="candidate_unbound",
        lever_resolution=None,
    )

    observation = JointSimulationPort(
        repo_root=REPO_ROOT,
        cycle_substrate_context=context,
    )(candidate=candidate, problem=problem, cycle_index=0)

    assert observation.status == "simulation_blocked"
    assert "world_identity_unresolved" in observation.authority_blockers
    assert observation.diagnostics["world_model_error_code"] == "world_identity_unresolved"
    assert observation.world_model_record is None


def test_joint_port_malformed_candidate_unbound_proof_does_not_inherit_context_wmr() -> None:
    """A typed refusal with invalid content binding cannot inherit the WMR."""

    problem, context = _lane0_cycle_context()
    malformed_refusal = _candidate_unbound_refusal(context).model_copy(
        update={"content_hash": "sha256:" + "0" * 64}
    )
    candidate = SimpleNamespace(
        candidate_id="candidate_unbound_malformed_refusal",
        status="candidate_unbound",
        lever_resolution=malformed_refusal,
    )

    observation = JointSimulationPort(
        repo_root=REPO_ROOT,
        cycle_substrate_context=context,
    )(candidate=candidate, problem=problem, cycle_index=0)

    assert observation.status == "simulation_blocked"
    assert "world_identity_unresolved" in observation.authority_blockers
    assert observation.diagnostics["world_model_error_code"] == "world_identity_unresolved"
    assert observation.world_model_record is None


@cache
def _canonical_strict_world_case() -> tuple[
    DesignProblem,
    CycleSubstrateContext,
    object,
]:
    """Build an N5-only fixture from frozen N4 semantics and the current WMR.

    The frozen N4 artifact is historical evidence.  The current N4 validator is
    expected to reject it until its owner reissues the WMR-bound receipt; that
    typed current red must not be promoted into a current N4 capability claim.
    The atom below is therefore re-bound and re-hashed explicitly as a test
    fixture; it is never parsed as, or presented as, an owner-issued N4 candidate.
    """

    from polisyos.runtime.quality.design_generation import ShadowGeneratedCandidate
    from polisyos.runtime.quality.intervention_atom_binding import (
        intervention_atom_content_hash,
    )
    from polisyos.runtime.quality.intervention_substrate import (
        production_composed_world_model_record,
    )
    from polisyos.runtime.quality.substrate_registry import (
        build_substrate_registry_from_existing_catalogs,
    )
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_contract,
    )

    n4_result = n4_contract.validate(REPO_ROOT)
    assert n4_result["status"] == "fail"
    assert n4_result["issues"] == [{"code": "current_wmr_reissue_receipt_owner_projection_drift"}]
    assert n4_result["outputs"] == [n4_contract.OUTPUT_PATH]
    payload = json.loads((REPO_ROOT / n4_contract.OUTPUT_PATH).read_text(encoding="utf-8"))
    frozen_candidate = ShadowGeneratedCandidate.model_validate(
        n4_contract.first_shadow_bound_recorded_candidate(payload)
    )
    problems = tuple(
        n4_contract._design_problem(recording)
        for recording in n4_contract._load_recordings(REPO_ROOT)
    )
    matched = tuple(
        problem
        for problem in problems
        if gy_content_hash(problem.model_dump(mode="json"))
        == frozen_candidate.atom.problem_frame_ref
    )
    assert len(matched) == 1
    problem = matched[0]
    world = production_composed_world_model_record(REPO_ROOT)
    atom_draft = frozen_candidate.atom.model_copy(
        update={"world_model_record_ref": world.world_model_record_id}
    )
    atom = atom_draft.model_copy(
        update={"content_hash": intervention_atom_content_hash(atom_draft)}
    )
    atom = InterventionAtomBinding.model_validate(atom.model_dump(mode="python"))
    candidate = SimpleNamespace(
        candidate_id=frozen_candidate.candidate_id,
        atom=atom,
    )
    registry = build_substrate_registry_from_existing_catalogs(REPO_ROOT)
    assert registry.content_hash == world.substrate_registry_ref.content_hash
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
    return problem, context, candidate


def _canonical_context_case_with_runtime_hints(
    runtime_hints: dict[str, Any],
) -> tuple[DesignProblem, CycleSubstrateContext, object]:
    """Rebind the strict candidate/context after adding request-shaping hints."""

    from polisyos.runtime.quality.intervention_atom_binding import (
        InterventionAtomBinding,
        intervention_atom_content_hash,
    )

    base_problem, base_context, base_candidate = _canonical_strict_world_case()
    problem = base_problem.model_copy(update={"runtime_hints": runtime_hints})
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    atom_draft = base_candidate.atom.model_copy(update={"problem_frame_ref": problem_ref})
    atom = atom_draft.model_copy(
        update={"content_hash": intervention_atom_content_hash(atom_draft)}
    )
    atom = InterventionAtomBinding.model_validate(atom.model_dump(mode="python"))
    candidate = SimpleNamespace(candidate_id=base_candidate.candidate_id, atom=atom)
    selected_hashes = tuple(base_context.selected_registry_entry_hashes)
    substrate_input_hash = gy_content_hash(
        {
            "design_problem_ref": problem_ref,
            "substrate_registry_content_hash": (base_context.substrate_registry_content_hash),
            "world_model_record_content_hash": (base_context.world_model_record_content_hash),
            "selected_registry_entry_hashes": selected_hashes,
        }
    )
    context = build_cycle_substrate_context(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_registry=base_context.substrate_registry,
        selected_registry_entry_hashes=selected_hashes,
        world_model_record=base_context.world_model_record,
        intervention_substrate=None,
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=None,
        substrate_input_content_hash=substrate_input_hash,
    )
    return problem, context, candidate


@_requires_owner_catalog
def test_joint_port_reuses_exact_cycle_context_wmr() -> None:
    """N5 receives the exact WMR object bound into the cycle context."""

    problem, context, candidate = _canonical_strict_world_case()

    observation = JointSimulationPort(
        repo_root=REPO_ROOT,
        cycle_substrate_context=context,
    )(
        candidate=candidate,
        problem=problem,
        cycle_index=0,
    )

    assert observation.world_model_record is context.world_model_record
    assert observation.diagnostics["world_model_source"] == "cycle_substrate_context"
    assert observation.k_world_ref_before == context.world_model_record.content_hash
    assert observation.k_world_ref_after == context.world_model_record.content_hash


@_requires_owner_catalog
def test_joint_port_accepts_label_drift_after_atom_world_resolution() -> None:
    """World identity follows resolved slots/content, never producer label equality."""

    problem, context, candidate = _canonical_strict_world_case()

    observation = JointSimulationPort(
        repo_root=REPO_ROOT,
        cycle_substrate_context=context,
    )(candidate=candidate, problem=problem, cycle_index=0)

    assert problem.domain == "ua_msme_cgf_decisive_capture"
    assert context.world_model_record.policy_domain == "fiscal_credit"
    assert observation.status == "simulation_pending_n5"
    assert observation.world_model_record is context.world_model_record
    assert observation.diagnostics["world_model_record_content_hash"] == (
        context.world_model_record.content_hash
    )
    assert observation.k_world_ref_before == context.world_model_record.content_hash


def _cyc01_owner_bound_n5_case(
    *,
    runtime_hints: dict[str, Any] | None = None,
) -> tuple[DesignProblem, CycleSubstrateContext, object]:
    """Build canonical atom/context inputs without granting an NCM source."""

    from polisyos.runtime.quality.intervention_atom_binding import (
        InterventionAtomBinding,
        intervention_atom_content_hash,
    )
    from tests.unit.runtime.quality.test_joint_simulation_horizon import _request

    hints = {
        "joint_simulation_budget_ref": f"budget://cyc-01/{uuid4().hex}/n5",
        "joint_simulation_horizon": {"start": 0, "end": 3, "step": 1},
        "joint_simulation_resource": "ncm_parallel_worlds",
    }
    if runtime_hints:
        hints.update(runtime_hints)
    problem = _problem(f"cyc_n5_owner_boundary_{uuid4().hex}").model_copy(
        update={"runtime_hints": hints}
    )
    registry = _lane0_registry(
        domain=problem.domain,
        source_id="l2_cyc:serializable_n5_builder.duckdb",
    )
    selected_hash = registry.entries[0].entry_content_hash
    world = _build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=problem,
        outcome="firm_survival",
        policy_slot_ids=("agents.income", "government.balance", "firm_survival"),
        substrate_registry=registry,
        selected_registry_entry_hashes=(selected_hash,),
    )
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    substrate_input_hash = gy_content_hash(
        {"domain": problem.domain, "registry": registry.content_hash}
    )
    context = build_cycle_substrate_context(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_registry=registry,
        selected_registry_entry_hashes=(selected_hash,),
        world_model_record=world,
        intervention_substrate=None,
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=gy_content_hash("cyc-n5-builder-pack"),
        substrate_input_content_hash=substrate_input_hash,
    )

    # The helper constructs strict InterventionAtomBinding DTOs in memory; it
    # is not an owner/source bundle and its ready request never enters the port.
    expected = _request(record=world, world_model_record_ref=world.world_model_record_id)
    atoms = []
    for atom in expected.intervention_atoms:
        rebound = atom.model_copy(update={"problem_frame_ref": problem_ref})
        rebound = rebound.model_copy(
            update={"content_hash": intervention_atom_content_hash(rebound)}
        )
        atoms.append(InterventionAtomBinding.model_validate(rebound.model_dump(mode="python")))
    atoms = tuple(atoms)
    candidate = SimpleNamespace(
        candidate_id="candidate_cyc_n5_builder",
        atom=atoms[0],
        intervention_atoms=atoms,
    )
    return problem, context, candidate


def test_joint_port_owner_missing_ncm_blocks_with_bound_wmr_provenance() -> None:
    """Absent owner NCM blocks N5 without dropping the already-resolved WMR."""

    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationRequest

    problem, context, candidate = _cyc01_owner_bound_n5_case()
    controller_calls: list[JointSimulationRequest] = []

    class _RecordingN5Controller:
        def run(self, concrete_request: JointSimulationRequest) -> object:
            controller_calls.append(concrete_request)
            raise AssertionError("owner-blocked NCM path must not invoke N5")

    port = JointSimulationPort(
        controller=_RecordingN5Controller(),
        repo_root=REPO_ROOT,
        cycle_substrate_context=context,
    )
    observation = port(candidate=candidate, problem=problem, cycle_index=0)

    assert observation.status == "simulation_blocked"
    assert observation.authority_blockers == ("joint_simulation_ncm_spec_missing",)
    assert observation.world_model_record is context.world_model_record
    assert observation.diagnostics["world_model_source"] == "cycle_substrate_context"
    assert observation.diagnostics["world_model_record_id"] == (
        context.world_model_record.world_model_record_id
    )
    assert observation.diagnostics["world_model_record_content_hash"] == (
        context.world_model_record.content_hash
    )
    assert observation.k_world_ref_before == context.world_model_record.content_hash
    assert observation.k_world_ref_after == context.world_model_record.content_hash
    assert observation.simulation_ref is None
    assert controller_calls == []



def _record_with_selected_ncm_ref(record: Any, ncm_ref: str) -> Any:
    """Rebind a fixture WMR to one selected NCM artifact without changing other fields."""

    from polisyos.runtime.quality.world_model_record import world_model_record_content_hash

    simulation_model_ref = record.simulation_model_ref.model_copy(
        update={"ncm_refs": (ncm_ref,)}
    )
    draft = record.model_copy(update={"simulation_model_ref": simulation_model_ref})
    content_hash = world_model_record_content_hash(draft)
    payload = draft.model_dump(mode="python")
    payload["content_hash"] = content_hash
    payload["world_model_record_id"] = (
        f"world_model_record_{content_hash.removeprefix('sha256:')[:16]}"
    )
    return type(record).model_validate(payload)


def _owner_n5_case_with_selected_ncm_ref(ncm_ref: str) -> tuple[Any, Any, Any]:
    """Build a content-valid owner context and candidate naming one selected NCM."""

    from polisyos.runtime.quality.intervention_atom_binding import (
        intervention_atom_content_hash,
    )

    problem, context, candidate = _cyc01_owner_bound_n5_case()
    world_record = _record_with_selected_ncm_ref(context.world_model_record, ncm_ref)
    context = build_cycle_substrate_context(
        design_problem_ref=context.design_problem_ref,
        domain=context.domain,
        substrate_registry=context.substrate_registry,
        selected_registry_entry_hashes=context.selected_registry_entry_hashes,
        world_model_record=world_record,
        intervention_substrate=context.intervention_substrate,
        candidate_levers=context.candidate_levers,
        transport_context=context.transport_context,
        source_pack_content_hash=context.source_pack_content_hash,
        substrate_input_content_hash=context.substrate_input_content_hash,
    )
    atoms = []
    for atom in candidate.intervention_atoms:
        rebound = atom.model_copy(
            update={"world_model_record_ref": world_record.world_model_record_id}
        )
        rebound = rebound.model_copy(
            update={"content_hash": intervention_atom_content_hash(rebound)}
        )
        atoms.append(type(atom).model_validate(rebound.model_dump(mode="python")))
    candidate = SimpleNamespace(
        candidate_id=candidate.candidate_id,
        atom=atoms[0],
        intervention_atoms=tuple(atoms),
    )
    return problem, context, candidate


def _runtime_ncm_fixture_store(
    tmp_path: Path, *, schema_version: str = "1.0"
) -> tuple[Any, Any, str]:
    """Persist one typed NCM through the same guarded tenant store used by N5."""

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.ir.analytics.ncm import persist_ncm_spec
    from polisyos.runtime.http.resilience import guard_runtime_cas
    from tests.unit.runtime.quality.test_joint_simulation_horizon import _ncm_with_cross_term

    store = guard_runtime_cas(
        FileSystemCAS(tmp_path / "runtime-cas").with_ambient_ownership_enforcement()
    )
    expected = _ncm_with_cross_term()
    try:
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            ref = persist_ncm_spec(
                store, expected, schema_version=schema_version
            )
        return store, expected, str(ref.artifact_id)
    except Exception:
        store.close()
        raise


def test_joint_port_uses_runtime_store_for_context_selected_ncm_and_keeps_no_context_control(
    tmp_path: Path,
) -> None:
    """N5 loads the exact selected model from its tenant store, with or without a context."""

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationRequest

    store, expected, ncm_ref = _runtime_ncm_fixture_store(tmp_path)
    repo_root = tmp_path / "empty-repo"
    request_seen: list[JointSimulationRequest] = []

    class _ReachedN5Error(RuntimeError):
        pass

    class _RecordingN5Controller:
        def run(self, concrete_request: JointSimulationRequest) -> object:
            request_seen.append(concrete_request)
            raise _ReachedN5Error("request reached the canonical N5 controller")

    try:
        problem, context, candidate = _owner_n5_case_with_selected_ncm_ref(ncm_ref)
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            # The resolver is independent of an optional CycleSubstrateContext.
            no_context_port = JointSimulationPort(
                repo_root=repo_root,
                artifact_store=store,
            )
            resolved_without_context = no_context_port._resolve_joint_simulation_ncm(
                problem=problem,
                world_record=context.world_model_record,
            )

            # The served N5 composition keeps the direct owner context and sends
            # its exact WMR-selected NCM to the canonical controller.
            served_port = JointSimulationPort(
                controller=_RecordingN5Controller(),
                repo_root=repo_root,
                cycle_substrate_context=context,
                artifact_store=store,
            )
            with pytest.raises(_ReachedN5Error):
                served_port(candidate=candidate, problem=problem, cycle_index=0)

        assert resolved_without_context.model_dump(mode="json") == expected.model_dump(
            mode="json"
        )
        assert len(request_seen) == 1
        assert request_seen[0].world_model_record.content_hash == (
            context.world_model_record.content_hash
        )
        assert request_seen[0].engine_plan[0].ncm_spec.model_dump(mode="json") == (
            expected.model_dump(mode="json")
        )
        assert not (repo_root / ".tmp" / "gy-s-composed-wmr-cas").exists()
    finally:
        store.close()


def test_joint_port_blocks_context_selected_ncm_owned_by_another_tenant(tmp_path: Path) -> None:
    """The served N5 path cannot read a selected NCM outside the active tenant scope."""

    from polisyos.core.security.tenant_context import tenant_scope

    store, _expected, ncm_ref = _runtime_ncm_fixture_store(tmp_path)
    try:
        problem, context, candidate = _owner_n5_case_with_selected_ncm_ref(ncm_ref)
        port = JointSimulationPort(
            repo_root=tmp_path / "empty-repo",
            cycle_substrate_context=context,
            artifact_store=store,
        )

        with tenant_scope(None, tenant_id="tenant-n5-foreign", cell_id="cell-n5-owner"):
            observation = port(candidate=candidate, problem=problem, cycle_index=0)

        assert observation.status == "simulation_blocked"
        assert observation.authority_blockers == ("joint_simulation_ncm_spec_unresolved",)
        diagnostic = observation.diagnostics["request_builder_error"]
        assert "read_manifest" in diagnostic
        assert "tenant-n5-foreign/cell-n5-owner" in diagnostic
        assert "tenant-n5-owner/cell-n5-owner" in diagnostic
        assert observation.world_model_record is context.world_model_record
    finally:
        store.close()


def test_joint_port_blocks_context_selected_ncm_absent_from_runtime_store(tmp_path: Path) -> None:
    """A well-shaped selected digest cannot resolve from a different or empty CAS root."""

    from polisyos.core.security.tenant_context import tenant_scope

    store, _expected, _stored_ref = _runtime_ncm_fixture_store(tmp_path)
    missing_ref = "sha256:" + "f" * 64
    repo_root = tmp_path / "empty-repo"
    try:
        problem, context, candidate = _owner_n5_case_with_selected_ncm_ref(missing_ref)
        port = JointSimulationPort(
            repo_root=repo_root,
            cycle_substrate_context=context,
            artifact_store=store,
        )

        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            observation = port(candidate=candidate, problem=problem, cycle_index=0)

        assert observation.status == "simulation_blocked"
        assert observation.authority_blockers == ("joint_simulation_ncm_spec_unresolved",)
        assert not (repo_root / ".tmp" / "gy-s-composed-wmr-cas").exists()
    finally:
        store.close()




def test_joint_port_blocks_selected_ncm_with_mismatched_manifest_schema(
    tmp_path: Path,
) -> None:
    """Matching bytes with an unsupported NCM manifest schema cannot enter N5."""

    from polisyos.core.security.tenant_context import tenant_scope

    store, _expected, ncm_ref = _runtime_ncm_fixture_store(tmp_path, schema_version="2.0")
    try:
        problem, context, candidate = _owner_n5_case_with_selected_ncm_ref(ncm_ref)
        port = JointSimulationPort(
            repo_root=tmp_path / "empty-repo",
            cycle_substrate_context=context,
            artifact_store=store,
        )

        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            observation = port(candidate=candidate, problem=problem, cycle_index=0)

        assert observation.status == "simulation_blocked"
        assert observation.authority_blockers == ("joint_simulation_ncm_spec_unresolved",)
        assert "selected_manifest_mismatch" in observation.diagnostics["request_builder_error"]
    finally:
        store.close()



def test_joint_port_refuses_selected_ncm_without_runtime_store(tmp_path: Path) -> None:
    """A selected digest cannot trigger N5's old repository-root CAS reconstruction."""

    problem, context, _candidate = _cyc01_owner_bound_n5_case()
    world_record = _record_with_selected_ncm_ref(
        context.world_model_record,
        "sha256:" + "0" * 64,
    )
    repo_root = tmp_path / "empty-repo"
    port = JointSimulationPort(repo_root=repo_root)

    with pytest.raises(WorldModelRecordError) as raised:
        port._resolve_joint_simulation_ncm(
            problem=problem,
            world_record=world_record,
        )

    assert raised.value.code == "joint_simulation_ncm_store_not_established"
    assert not (repo_root / ".tmp" / "gy-s-composed-wmr-cas").exists()




def test_joint_port_reports_runtime_ncm_store_unavailability_as_typed_block(
    tmp_path: Path,
) -> None:
    """A guarded-store outage is an N5 limitation, not an exception escape."""

    from polisyos.runtime.http.errors import RuntimeDependencyUnavailableError

    problem, context, _candidate = _cyc01_owner_bound_n5_case()
    world_record = _record_with_selected_ncm_ref(
        context.world_model_record,
        "sha256:" + "1" * 64,
    )

    class _UnavailableNcmStore:
        def get_manifest(self, _artifact_id: object) -> object:
            raise RuntimeDependencyUnavailableError(
                "content_addressed_storage",
                detail="fixture store unavailable",
            )

    port = JointSimulationPort(
        repo_root=tmp_path / "empty-repo",
        artifact_store=_UnavailableNcmStore(),
    )
    with pytest.raises(WorldModelRecordError) as raised:
        port._resolve_joint_simulation_ncm(
            problem=problem,
            world_record=world_record,
        )

    assert raised.value.code == "joint_simulation_ncm_store_unavailable"



def test_joint_port_preserves_typed_missing_ncm_ref_without_context(tmp_path: Path) -> None:
    """No context and no selected NCM keep the existing typed N5 limitation."""

    problem, context, _candidate = _cyc01_owner_bound_n5_case()
    repo_root = tmp_path / "empty-repo"
    port = JointSimulationPort(repo_root=repo_root)

    with pytest.raises(WorldModelRecordError) as raised:
        port._resolve_joint_simulation_ncm(
            problem=problem,
            world_record=context.world_model_record,
        )

    assert raised.value.code == "joint_simulation_ncm_spec_missing"
    assert not (repo_root / ".tmp" / "gy-s-composed-wmr-cas").exists()


@pytest.mark.parametrize("hostile_location", ("runtime_hint", "engine_plan"))
def test_joint_port_rejects_unverified_ncm_authority_sources(hostile_location: str) -> None:
    """Neither caller hints nor nested plans can replace the owner NCM resolver."""

    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
        JointSimulationRequest,
        JointSimulationResult,
    )

    # This payload is deliberately caller-provided and non-authoritative. Keep
    # it inline so the rejection witness cannot depend on the N5 fixture helper
    # or accidentally promote a test-built NCM into the owner boundary.
    hostile_ncm_payload = {
        "endogenous_vars": ["income_delta", "balance_delta", "firm_survival"],
        "exogenous_specs": [
            {
                "variable": "u_income",
                "associated_endogenous": "income_delta",
            },
            {
                "variable": "u_balance",
                "associated_endogenous": "balance_delta",
            },
            {
                "variable": "u_survival",
                "associated_endogenous": "firm_survival",
            },
        ],
        "structural_equations": [
            {
                "variable": "income_delta",
                "parents": [],
                "exogenous": "u_income",
                "equation_type": "linear",
                "equation_params": {"intercept": 0.0, "coefficients": {}},
            },
            {
                "variable": "balance_delta",
                "parents": [],
                "exogenous": "u_balance",
                "equation_type": "linear",
                "equation_params": {"intercept": 0.0, "coefficients": {}},
            },
            {
                "variable": "firm_survival",
                "parents": ["income_delta", "balance_delta"],
                "exogenous": "u_survival",
                "equation_type": "nonlinear",
                "equation_params": {
                    "noise_expression": (
                        "1.0 + (2.0 * income_delta) + (3.0 * balance_delta) "
                        "+ (5.0 * income_delta * balance_delta) + u"
                    ),
                },
            },
        ],
        "is_acyclic": True,
        "markov_condition_verified": True,
        "independence_model": "dag_markov",
        "fit_method": "caller_payload",
    }
    if hostile_location == "runtime_hint":
        hostile_hints = {"joint_simulation_ncm_spec": hostile_ncm_payload}
    else:
        hostile_hints = {
            "joint_simulation_engine_plan": {
                "engine_kind": "ncm_parallel_worlds",
                "objective_ref": "objective://firm_survival",
                "ncm_spec": hostile_ncm_payload,
                "variable_map": {
                    "agents.income": "income_delta",
                    "government.balance": "balance_delta",
                    "firm_survival": "firm_survival",
                },
                "eligibility_conditions": ("acyclic", "counterfactual_do_worlds"),
            }
        }
    problem, context, candidate = _cyc01_owner_bound_n5_case(runtime_hints=hostile_hints)
    controller_calls: list[JointSimulationRequest] = []
    real_n5 = JointSimulationHorizonController()

    class _RecordingN5Controller:
        def run(self, concrete_request: JointSimulationRequest) -> JointSimulationResult:
            controller_calls.append(concrete_request)
            return real_n5.run(concrete_request)

    observation = JointSimulationPort(
        controller=_RecordingN5Controller(),
        repo_root=REPO_ROOT,
        cycle_substrate_context=context,
    )(candidate=candidate, problem=problem, cycle_index=0)

    assert observation.status == "simulation_blocked"
    assert observation.authority_blockers == ("joint_simulation_ncm_spec_missing",)
    assert observation.world_model_record is context.world_model_record
    assert observation.k_world_ref_before == context.world_model_record.content_hash
    assert observation.k_world_ref_after == context.world_model_record.content_hash
    assert controller_calls == []


def test_joint_port_rejects_changed_problem_and_catalog_after_owner_block() -> None:
    """The owner-blocked path retains the existing identity refusal boundaries."""

    problem, context, candidate = _cyc01_owner_bound_n5_case()
    port = JointSimulationPort(repo_root=REPO_ROOT, cycle_substrate_context=context)
    problem_ref = context.design_problem_ref

    foreign_problem = problem.model_copy(update={"domain": "foreign_cyc_domain"})
    rejected_problem = port(candidate=candidate, problem=foreign_problem, cycle_index=0)
    assert rejected_problem.status == "simulation_blocked"
    assert "cycle_substrate_design_problem_mismatch" in rejected_problem.authority_blockers

    foreign_registry = _lane0_registry(
        domain=problem.domain,
        source_id="l2_cyc:changed_catalog.duckdb",
    )
    foreign_hash = foreign_registry.entries[0].entry_content_hash
    foreign_world = _build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=problem,
        outcome="firm_survival",
        policy_slot_ids=("agents.income", "government.balance", "firm_survival"),
        substrate_registry=foreign_registry,
        selected_registry_entry_hashes=(foreign_hash,),
    )
    foreign_context = build_cycle_substrate_context(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_registry=foreign_registry,
        selected_registry_entry_hashes=(foreign_hash,),
        world_model_record=foreign_world,
        intervention_substrate=None,
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=gy_content_hash("cyc-n5-changed-catalog"),
        substrate_input_content_hash=gy_content_hash(
            {"domain": problem.domain, "registry": foreign_registry.content_hash}
        ),
    )
    rejected_catalog = JointSimulationPort(
        repo_root=REPO_ROOT,
        cycle_substrate_context=foreign_context,
    )(candidate=candidate, problem=problem, cycle_index=0)
    assert rejected_catalog.status == "simulation_blocked"
    assert "world_identity_unresolved" in rejected_catalog.authority_blockers


def test_real_unsupported_n5_result_is_serialized_as_simulation_blocked() -> None:
    """A real gated N5 receipt cannot be relabeled as a completed simulation."""

    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
    )
    from tools.quality.validation import (
        check_layer3_gy_joint_simulation_horizon_contract as n5_contract,
    )

    request = n5_contract._request().model_copy(
        update={"coupling_graph": n5_contract._coupling_graph("feedback")}
    )
    result = JointSimulationHorizonController().run(request)

    status, blockers = _joint_simulation_port_outcome(result)

    assert result.receipt.calibration_status == "unsupported_coupling_gated"
    assert not result.trajectories
    assert status == "simulation_blocked", "unsupported_n5_result_must_block"
    assert "unsupported_coupling_class:feedback" in blockers
    assert "n5_coupling_blocked" in blockers


def test_n5_coupling_blocker_survives_selected_summary_projection() -> None:
    """The typed N5 blocker reaches the exact summary N9 consumes."""

    summary = _open_world_summary("candidate_n5_coupling_blocked")
    simulation = SimulationPortObservation(
        candidate_id=summary.candidate_id,
        status="simulation_blocked",
        authority_blockers=(
            "unsupported_coupling_class:feedback",
            "n5_coupling_blocked",
        ),
    )
    value = ValuePortObservation(
        candidate_id=summary.candidate_id,
        authority_blockers=(),
    )

    projected = _summary_with_value_observation(
        summary,
        simulation=simulation,
        value_port=value,
        counterexample_ref="counterexample://n5/coupling",
    )

    assert projected.value_blockers == ("n5_coupling_blocked",)


@_requires_owner_catalog
def test_joint_port_rejects_candidate_ref_mismatched_to_context_wmr() -> None:
    """A candidate's shaped WMR ref cannot override the resolved context world."""

    from polisyos.runtime.quality.intervention_atom_binding import (
        InterventionAtomBinding,
        intervention_atom_content_hash,
    )

    problem, context, canonical_candidate = _canonical_strict_world_case()
    draft = canonical_candidate.atom.model_copy(
        update={"world_model_record_ref": "world_model_record_0123456789abcdef"}
    )
    atom = draft.model_copy(update={"content_hash": intervention_atom_content_hash(draft)})
    atom = InterventionAtomBinding.model_validate(atom.model_dump(mode="python"))
    candidate = SimpleNamespace(
        candidate_id="candidate_first_vertical_wrong_world",
        atom=atom,
    )

    observation = JointSimulationPort(
        repo_root=REPO_ROOT,
        cycle_substrate_context=context,
    )(candidate=candidate, problem=problem, cycle_index=0)

    assert observation.status == "simulation_blocked"
    assert "world_identity_unresolved" in observation.authority_blockers


@_requires_owner_catalog
def test_cycle_world_identity_rejects_shaped_atom_even_when_strings_match() -> None:
    """Matching ref/slot strings are not a substitute for the strict atom owner."""

    _problem_value, context, _candidate = _canonical_strict_world_case()
    shaped = _Atom(
        "candidate_shaped_world_identity",
        "sha256:" + "7" * 64,
        world_model_record_ref=context.world_model_record.content_hash,
        target_world_slots=("global.tax_rate",),
    )

    with pytest.raises(WorldModelRecordError, match="world_identity_unresolved"):
        resolve_cycle_substrate_world_identity(context, atom=shaped)


@_requires_owner_catalog
def test_cycle_world_identity_rejects_atom_from_another_problem() -> None:
    """A valid atom cannot cross a DesignProblem boundary within the same world."""

    from polisyos.runtime.quality.intervention_atom_binding import (
        InterventionAtomBinding,
        intervention_atom_content_hash,
    )

    _problem_value, context, candidate = _canonical_strict_world_case()
    draft = candidate.atom.model_copy(update={"problem_frame_ref": "sha256:" + "9" * 64})
    atom = draft.model_copy(update={"content_hash": intervention_atom_content_hash(draft)})
    atom = InterventionAtomBinding.model_validate(atom.model_dump(mode="python"))

    with pytest.raises(WorldModelRecordError, match="world_identity_unresolved"):
        resolve_cycle_substrate_world_identity(context, atom=atom)


@_requires_owner_catalog
def test_joint_port_rejects_empty_atom_slots_as_unresolved_world_identity() -> None:
    """A world ref without at least one resolved slot is not world identity."""

    from polisyos.runtime.quality.intervention_atom_binding import (
        InterventionAtomBinding,
        intervention_atom_content_hash,
    )

    problem, context, canonical_candidate = _canonical_strict_world_case()
    draft = canonical_candidate.atom.model_copy(update={"target_world_slots": ()})
    atom = draft.model_copy(update={"content_hash": intervention_atom_content_hash(draft)})
    atom = InterventionAtomBinding.model_validate(atom.model_dump(mode="python"))
    candidate = SimpleNamespace(candidate_id="candidate_empty_slots", atom=atom)

    observation = JointSimulationPort(
        repo_root=REPO_ROOT,
        cycle_substrate_context=context,
    )(candidate=candidate, problem=problem, cycle_index=0)

    assert observation.status == "simulation_blocked"
    assert "world_identity_unresolved" in observation.authority_blockers


@_requires_owner_catalog
def test_joint_port_types_tampered_strict_atom_as_unresolved_world_identity() -> None:
    """A model-constructed atom with a stale hash fails closed at the port."""

    problem, context, canonical_candidate = _canonical_strict_world_case()
    atom = canonical_candidate.atom.model_copy(update={"content_hash": "sha256:" + "0" * 64})
    candidate = SimpleNamespace(candidate_id="candidate_tampered_atom", atom=atom)

    observation = JointSimulationPort(
        repo_root=REPO_ROOT,
        cycle_substrate_context=context,
    )(candidate=candidate, problem=problem, cycle_index=0)

    assert observation.status == "simulation_blocked"
    assert "world_identity_unresolved" in observation.authority_blockers


@_requires_owner_catalog
def test_explicit_joint_request_cannot_bypass_context_wmr() -> None:
    """An explicit N5 request with another concrete WMR is refused before simulation."""

    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationRequest,
    )

    base_problem, base_context, _base_candidate = _canonical_strict_world_case()
    request_registry = _lane0_registry(
        domain="first_vertical_request_probe",
        source_id="l2_watershed_graph:explicit_request.duckdb",
    )
    request_world = _build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=base_problem,
        outcome="employment_retention",
        policy_slot_ids=("global.tax_rate",),
        substrate_registry=request_registry,
        selected_registry_entry_hashes=(request_registry.entries[0].entry_content_hash,),
    )
    request = JointSimulationRequest.model_construct(
        world_model_record_ref=request_world.world_model_record_id,
        world_model_record=request_world,
    )
    problem, context, candidate = _canonical_context_case_with_runtime_hints(
        {"joint_simulation_request": request}
    )
    assert context.world_model_record.content_hash == base_context.world_model_record.content_hash
    calls: list[object] = []

    class _RecordingController:
        def run(self, concrete_request: object) -> object:
            calls.append(concrete_request)
            return SimpleNamespace(
                receipt=SimpleNamespace(payload_hash="sha256:" + "1" * 64),
                uncertainty_kind="K_sim",
                promotion_ready_value_packet={},
                engine_decisions=(),
                trajectories=(),
                interaction_terms=(),
            )

    observation = JointSimulationPort(
        controller=_RecordingController(),
        repo_root=REPO_ROOT,
        cycle_substrate_context=context,
    )(candidate=candidate, problem=problem, cycle_index=0)

    assert observation.status == "simulation_blocked"
    assert "cycle_substrate_request_wmr_mismatch" in observation.authority_blockers
    assert calls == []


@_requires_owner_catalog
def test_explicit_joint_request_atom_refs_bind_before_injected_controller() -> None:
    """A valid nested atom for another world is refused at the single N5 intake."""

    from polisyos.runtime.quality.intervention_atom_binding import (
        InterventionAtomBinding,
        intervention_atom_content_hash,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationRequest,
    )
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_contract,
    )

    base_problem, base_context, _base_candidate = _canonical_strict_world_case()
    n4_payload = json.loads(
        (
            REPO_ROOT / "architecture/policy_design_case/layer3_gy_design_generation_contract.json"
        ).read_text(encoding="utf-8")
    )
    candidate_payload = n4_contract.first_shadow_bound_recorded_candidate(n4_payload)
    atom = InterventionAtomBinding.model_validate(candidate_payload["atom"])
    mismatched_atom = atom.model_copy(
        update={"world_model_record_ref": "world_model_record_0123456789abcdef"}
    )
    mismatched_atom = mismatched_atom.model_copy(
        update={"content_hash": intervention_atom_content_hash(mismatched_atom)}
    )
    mismatched_atom = InterventionAtomBinding.model_validate(
        mismatched_atom.model_dump(mode="python")
    )
    request = JointSimulationRequest.model_construct(
        world_model_record_ref=base_context.world_model_record.world_model_record_id,
        world_model_record=base_context.world_model_record,
        intervention_atoms=(mismatched_atom,),
    )
    problem, context, candidate = _canonical_context_case_with_runtime_hints(
        {"joint_simulation_request": request}
    )
    assert problem.domain == base_problem.domain
    assert context.world_model_record.content_hash == base_context.world_model_record.content_hash
    calls: list[object] = []

    class _RecordingController:
        def run(self, concrete_request: object) -> object:
            calls.append(concrete_request)
            return SimpleNamespace(
                receipt=SimpleNamespace(payload_hash="sha256:" + "3" * 64),
                uncertainty_kind="K_sim",
                promotion_ready_value_packet={},
                engine_decisions=(),
                trajectories=(),
                interaction_terms=(),
            )

    observation = JointSimulationPort(
        controller=_RecordingController(),
        repo_root=REPO_ROOT,
        cycle_substrate_context=context,
    )(candidate=candidate, problem=problem, cycle_index=0)

    assert observation.status == "simulation_blocked"
    assert "world_identity_unresolved" in observation.authority_blockers
    assert calls == []


@_requires_owner_catalog
def test_explicit_request_nested_atom_missing_slot_fails_world_identity() -> None:
    """Every nested request atom resolves before any N5 controller injection."""

    from polisyos.runtime.quality.intervention_atom_binding import (
        InterventionAtomBinding,
        intervention_atom_content_hash,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationRequest,
    )

    problem, context, candidate = _canonical_strict_world_case()
    draft = candidate.atom.model_copy(
        update={
            "target_world_slots": ("missing.world_slot",),
            "normalized_from": None,
        }
    )
    nested_atom = draft.model_copy(update={"content_hash": intervention_atom_content_hash(draft)})
    nested_atom = InterventionAtomBinding.model_validate(nested_atom.model_dump(mode="python"))
    request = JointSimulationRequest.model_construct(
        world_model_record_ref=context.world_model_record.world_model_record_id,
        world_model_record=context.world_model_record,
        intervention_atoms=(nested_atom,),
    )
    problem = problem.model_copy(update={"runtime_hints": {"joint_simulation_request": request}})
    calls: list[object] = []

    observation = JointSimulationPort(
        controller=SimpleNamespace(run=lambda concrete: calls.append(concrete)),
        repo_root=REPO_ROOT,
    )(candidate=candidate, problem=problem, cycle_index=0)

    assert observation.status == "simulation_blocked"
    assert observation.authority_blockers == ("world_identity_unresolved",)
    assert calls == []


def test_joint_port_cache_key_tracks_canonical_registry_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A changed canonical registry rebuilds the WMR instead of reusing stale world state."""

    from polisyos.runtime.quality import generation_cycle

    problem, _context = _lane0_cycle_context()
    first_registry = _lane0_registry(
        domain="water_quality",
        source_id="l2_watershed_graph:causal_edges.v1.duckdb",
    )
    second_registry = _lane0_registry(
        domain="water_quality",
        source_id="l2_watershed_graph:causal_edges.v2.duckdb",
    )
    registries = iter((first_registry, second_registry))

    def _next_registry(_repo_root: Path) -> SubstrateRegistry:
        return next(registries)

    monkeypatch.setattr(
        generation_cycle,
        "build_substrate_registry_from_existing_catalogs",
        _next_registry,
    )
    candidate = _Candidate(
        candidate_id="candidate_water_quality_cache",
        atom=_Atom(
            "candidate_water_quality_cache",
            "sha256:" + "d" * 64,
            world_model_record_ref=None,
            target_world_slots=("nitrate_load",),
        ),
        diversity_key=("buffer", "watershed", "water", "cache"),
    )
    port = JointSimulationPort(repo_root=REPO_ROOT)

    first = port(candidate=candidate, problem=problem, cycle_index=0)
    second = port(candidate=candidate, problem=problem, cycle_index=1)

    assert first.world_model_record is not None
    assert second.world_model_record is not None
    assert first.world_model_record.content_hash != second.world_model_record.content_hash
    assert (
        first.world_model_record.substrate_registry_ref.content_hash == first_registry.content_hash
    )
    assert (
        second.world_model_record.substrate_registry_ref.content_hash
        == second_registry.content_hash
    )


def test_joint_port_revalidates_context_before_reusing_wmr() -> None:
    """A stale registry checksum cannot retain an old WMR through the context route."""

    _problem_value, context = _lane0_cycle_context()
    stale_context = context.model_copy(
        update={"substrate_registry_content_hash": "sha256:" + "e" * 64}
    )

    with pytest.raises(ValueError, match="cycle_substrate_registry_hash_mismatch"):
        JointSimulationPort(
            repo_root=REPO_ROOT,
            cycle_substrate_context=stale_context,
        )


@_requires_owner_catalog
def test_shaped_wmr_ref_without_resolved_object_is_rejected() -> None:
    """A WMR-looking string cannot substitute for a resolved owner object."""

    problem = _problem("shaped_wmr_ref").model_copy(
        update={"runtime_hints": {"world_model_record_ref": "world_model_record_0123456789abcdef"}}
    )
    candidate = _Candidate(
        candidate_id="candidate_shaped_wmr",
        atom=_Atom("candidate_shaped_wmr", "sha256:" + "c" * 64),
        diversity_key=("grant", "firms", "shaped", "wmr"),
    )

    observation = JointSimulationPort(repo_root=REPO_ROOT)(
        candidate=candidate,
        problem=problem,
        cycle_index=0,
    )

    assert observation.status == "simulation_blocked"
    assert "world_model_record_unresolved" in observation.authority_blockers


@pytest.mark.asyncio
async def test_missing_canonical_registry_never_mints_n6_bootstrap_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N7 remains requested when S0 is unavailable; N6 mints no registry."""

    from polisyos.runtime.quality import generation_cycle

    def _owner_unavailable(_repo_root: Path) -> SubstrateRegistry:
        raise FileNotFoundError("lane0 owner unavailable")

    monkeypatch.setattr(
        generation_cycle,
        "build_substrate_registry_from_existing_catalogs",
        _owner_unavailable,
    )
    run = await GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_AcquisitionGrounding(),
        value_port=PendingN8ValuePort(),
        promotion_port=_NoPromotionPort(),
        authority_scope="contract_testing",
        acquisition_owner_gateway=RecordedAcquisitionOwnerGateway(artifacts_by_requirement={}),
        repo_root=REPO_ROOT,
    ).run(
        _problem("missing_canonical_registry"),
        budget_state=_budget(),
        min_cycles=1,
        max_cycles=1,
    )

    cycle = run.cycles[0]
    assert cycle.terminal_kind == "acquisition_required"
    assert cycle.acquisition_receipt is None
    assert "n7_substrate_registry_unresolved" in cycle.counterexample.diagnostic.code
    assert "n7_substrate_registry_unresolved" not in cycle.grounding.issue_codes
    assert "n7_route" not in cycle.revision_request.strategy_payload
    assert "n6.bootstrap" not in json.dumps(run.model_dump(mode="json"))


def test_boundary_wmr_uses_injected_registry_and_problem_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The canonical boundary owner must not rebuild or stamp first-vertical scope."""

    from polisyos.runtime.quality import generation_cycle

    registry = _lane0_registry(
        domain="water_quality",
        source_id="l2_watershed_graph:causal_edges.duckdb",
    )
    problem = _domain_problem(
        domain="water_quality",
        region="dnieper_basin",
        valid_time="2021/2024",
        as_of="2026-07-12",
        outcome="nitrate_load",
        stakeholder_id="watershed_communities",
    )

    def _unexpected_registry_rebuild(_repo_root: Path) -> SubstrateRegistry:
        raise AssertionError("injected_registry_was_ignored")

    monkeypatch.setattr(
        generation_cycle,
        "build_substrate_registry_from_existing_catalogs",
        _unexpected_registry_rebuild,
    )
    record = _build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=problem,
        outcome="nitrate_load",
        policy_slot_ids=("nitrate_load",),
        substrate_registry=registry,
        selected_registry_entry_hashes=(registry.entries[0].entry_content_hash,),
    )

    assert record.policy_domain == "water_quality"
    assert record.region_or_jurisdiction == "dnieper_basin"
    assert record.valid_time_scope == "2021/2024"
    assert record.tx_time_scope == "2026-07-12"
    assert "watershed_communities" in record.population_scope
    assert record.substrate_registry_ref.content_hash == registry.content_hash
    assert {item.entry_content_hash for item in record.substrate_registry_ref.resolved_entries} == {
        registry.entries[0].entry_content_hash
    }
    assert not record.fabric_world_ref.snapshot_root.startswith("/")
    assert "UA" not in json.dumps(record.model_dump(mode="json"))


def test_boundary_wmr_rejects_selected_entry_absent_from_registry() -> None:
    """A shaped selected hash cannot become a boundary-world authority receipt."""

    registry = _lane0_registry(
        domain="water_quality",
        source_id="l2_watershed_graph:causal_edges.duckdb",
    )
    problem = _domain_problem(
        domain="water_quality",
        region="dnieper_basin",
        valid_time="2021/2024",
        as_of="2026-07-12",
        outcome="nitrate_load",
        stakeholder_id="watershed_communities",
    )

    with pytest.raises(WorldModelRecordError, match="boundary_registry_entry_unresolved"):
        _build_boundary_world_model_record(
            repo_root=REPO_ROOT,
            problem=problem,
            outcome="nitrate_load",
            policy_slot_ids=("nitrate_load",),
            substrate_registry=registry,
            selected_registry_entry_hashes=("sha256:" + "0" * 64,),
        )


def _budget(max_usd: str = "5.0") -> BudgetState:
    return BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=Decimal(max_usd))},
    )


def _n7_data_requirement_spec() -> DataRequirementSpec:
    return DataRequirementSpec(
        requirement_id="data-requirement:owner-panel-missing",
        claim_id="claim-owner-panel-missing",
        required_data_families=("owner_panel_missing",),
        scope=DataRequirementScope(
            population="firms",
            geography="UA",
            time="annual",
            time_role="observation_time",
        ),
        recency_horizon="P90D",
        lineage_strictness="strict",
        quality_minima=DataQualityMinimums(min_quality_score=0.8, min_completeness=0.95),
        missingness_tolerance=0.02,
        transformation_tolerance="none",
        admissibility_predicates=("source_family_matches_compiled_requirement",),
        mandatory_facets=("source_contract_ref", "lineage_refs"),
        concept_spine_refs=("concept:firm",),
        authority_profile_refs=("authority_profile.research",),
    )


def _canonical_n7_test_atom(
    problem: DesignProblem,
    *,
    candidate_id: str,
    target_world_slot: str,
) -> InterventionAtomBinding:
    """Build a content-valid canonical atom for the isolated N7 consumer test."""

    from polisyos.ir.analytics.interventions import (
        ProofKernelInterventionType,
        QueryTargetKind,
    )
    from polisyos.runtime.quality.intervention_atom_binding import (
        CausalDoExpression,
        DirectEffectBundle,
        IdentificationPlanRef,
        IntendedDownstreamEstimand,
        InterventionAtomBinding,
        OperatorKind,
        TargetSelectorBinding,
        _content_payload_from_fields,
    )

    proof_type = ProofKernelInterventionType.NODE
    selector_ref = gy_content_hash({"target_world_slot": target_world_slot})
    fields = {
        "schema_version": "policyos.runtime.intervention_atom_binding.v1",
        "problem_frame_ref": gy_content_hash(problem.model_dump(mode="json")),
        "policy_spec_ref": gy_content_hash({"policy_spec": candidate_id}),
        "intervention_id": candidate_id,
        "operator_kind": OperatorKind(
            trinity_kind="probe",
            proof_kernel_type=proof_type,
        ),
        "target_selector": TargetSelectorBinding(
            trinity_target={"scope": "all"},
            selector_content_ref=selector_ref,
        ),
        "target_world_slots": (target_world_slot,),
        "read_slots": (),
        "direct_effect_bundle": DirectEffectBundle(
            params={"candidate": candidate_id},
            schedule={"kind": "immediate"},
            mechanism_id="tests.n7.candidate",
        ),
        "causal_do_expr": CausalDoExpression(
            intervention_type=proof_type,
            expression_payload={"intervention_type": "node", "assignments": []},
            write_variables=(target_world_slot,),
            selection_context_ref=selector_ref,
        ),
        "intended_downstream_estimand": IntendedDownstreamEstimand(
            target_kind=QueryTargetKind.EXPECTATION,
            outcome_variables=(target_world_slot,),
        ),
        "causal_path_or_identification_plan_ref": IdentificationPlanRef(
            plan_ref=gy_content_hash({"identification_plan": candidate_id}),
            intervention_type=proof_type,
            backend="test_fixture",
            status="identified",
            theorem_family="test_fixture",
        ),
        "world_model_record_ref": "world_model_record_test",
        "measurement_expectations": {},
        "measurement_expectations_authority": "supporting_metadata",
        "normalized_from": None,
        "producer_ref": "tests.unit.runtime.quality.test_generation_cycle",
        "provenance_refs": ("fixture:n7-candidate",),
        "status": "candidate_unverified",
    }
    content_hash = gy_content_hash(_content_payload_from_fields(fields))
    return InterventionAtomBinding.model_validate(
        {
            **fields,
            "atom_id": f"atom_{content_hash.removeprefix('sha256:')[:16]}",
            "content_hash": content_hash,
        }
    )


def _n7_owner_payload(
    *,
    acquired_family: str,
    source_id: str,
    candidate_id: str,
    candidate_content_hash: str,
    target_world_slots: tuple[str, ...],
) -> dict[str, object]:
    owner_response: dict[str, object] = {
        "owner_response_kind": "recorded_unit_owner_response",
        "acquired_family": acquired_family,
        "source_id": source_id,
        "candidate_id": candidate_id,
    }
    return {
        "owner_response_kind": "real_owner_capture",
        "owner_response": owner_response,
        "raw_owner_response_hash": _n7_stable_json_hash(owner_response),
        "acquired_substrate_registrations": [
            _n7_registration(
                source_id=source_id,
                family_id=acquired_family,
                snapshot_id=f"snapshot:{acquired_family}:2026-07-05",
            ).model_dump(mode="json")
        ],
        "candidate_bindings": [
            {
                "candidate_id": candidate_id,
                "candidate_content_hash": candidate_content_hash,
                "target_world_slots": list(target_world_slots),
            }
        ],
    }


def _n7_stable_json_hash(value: dict[str, object]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _n9_receipt(
    candidate_id: str,
    *,
    consumer_promotable: bool,
    promotion_lane: str = "production",
    non_promotable_reason: str | None = None,
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "promoted": True,
        "promotion_lane": promotion_lane,
        "consumer_promotable": consumer_promotable,
        "non_promotable_reason": non_promotable_reason,
    }


def _n7_substrate_registry() -> SubstrateRegistry:
    entry = build_substrate_registry_entry(
        _n7_registration(
            source_id="baseline.owner_panel_missing",
            family_id="owner_panel_missing",
            snapshot_id="baseline:owner_panel_missing",
        )
    )
    return build_substrate_registry(
        (entry,),
        producer_ref="tests.unit.runtime.quality.test_generation_cycle",
        source_catalog_refs=("test://n6-n7/substrate-registry",),
    )


def _n7_registration(*, source_id: str, family_id: str, snapshot_id: str) -> SubstrateRegistration:
    return SubstrateRegistration(
        source_id=source_id,
        family_id=family_id,
        layer=SubstrateLayer.L1,
        coverage=SubstrateCoverage(
            coverage_score=0.9,
            coverage_kind="recorded_owner_response",
            coverage_rule_ref=f"test://coverage/{family_id}",
            dataset_count=1,
            metric_binding_count=1,
            observation_count=1,
        ),
        trust_tier=SubstrateTrustTier(
            tier="recorded",
            trust_cap=0.8,
            trust_multiplier=0.8,
            authority_ref=f"test://trust/{family_id}",
        ),
        identification_mode="observed_panel",
        schema_regime=SubstrateSchemaRegime(
            schema_regime_id=f"manifest:{family_id}",
            authority_ref=f"test://schema/{family_id}",
        ),
        data_version="2026-07-05",
        snapshot_id=snapshot_id,
        source_snapshot_id=snapshot_id,
        provenance_refs=(f"test://provenance/{source_id}",),
        authority_refs=(f"test://authority/{family_id}",),
    )


def _real_n4_generation_result_with_candidate() -> tuple[dict[str, Any], dict[str, Any]]:
    """Select one content-matched real candidate without pinning a receipt-local id."""

    payload = json.loads(
        (
            REPO_ROOT / "architecture/policy_design_case/layer3_gy_design_generation_contract.json"
        ).read_text(encoding="utf-8")
    )
    for result in payload["generation_results"]:
        dispositions = {
            item.get("candidate_id"): item
            for item in result.get("grounding_dispositions") or ()
            if item.get("candidate_id")
        }
        for candidate in result.get("candidates") or ():
            disposition = dispositions.get(candidate.get("candidate_id"))
            if disposition is not None and disposition.get(
                "shadow_atom_content_hash"
            ) == candidate.get("atom", {}).get("content_hash"):
                return result, candidate
    raise AssertionError("missing content-matched real N4 candidate")


def _recorded_problem_for_candidate(candidate: dict[str, Any]) -> DesignProblem:
    """Resolve the exact historical basis named by a recorded N4 candidate."""

    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_contract,
    )

    expected_ref = str(candidate["atom"]["problem_frame_ref"])
    matches = tuple(
        n4_contract._design_problem(recording)
        for recording in n4_contract._load_recordings(REPO_ROOT)
        if gy_content_hash(
            n4_contract._design_problem(recording).model_dump(mode="json")
        )
        == expected_ref
    )
    assert len(matches) == 1
    return matches[0]


def _real_cg4_proxy_gap_result() -> tuple[dict[str, Any], dict[str, Any]]:
    cg4_payload = json.loads(
        (
            REPO_ROOT / "architecture/policy_design_case/grounding_phrasing_defense_contract.json"
        ).read_text(encoding="utf-8")
    )
    handoff = next(
        item
        for item in cg4_payload["certificate"]["quarantine_handoffs"]
        if item["action"] == "adversarial_validate"
    )
    result, candidate = _real_n4_generation_result_with_candidate()
    disposition = copy.deepcopy(
        next(
            item
            for item in result["grounding_dispositions"]
            if item.get("candidate_id") == candidate["candidate_id"]
        )
    )
    candidate = copy.deepcopy(candidate)
    disposition["candidate_id"] = candidate["candidate_id"]
    disposition["shadow_atom_content_hash"] = candidate["atom"]["content_hash"]
    disposition["disposition"] = "shadow_bound"
    disposition["certificate_chain"] = {
        **(disposition.get("certificate_chain") or {}),
        "quarantine_handoff": handoff,
    }
    return {
        "status": "generated",
        "design_problem_ref": result["design_problem_ref"],
        "candidates": [candidate],
        "grounding_dispositions": [disposition],
    }, candidate


@pytest.mark.asyncio
async def test_controller_runs_counterexample_driven_revision_over_two_real_cycles() -> None:
    generator = _CounterexampleAwareGenerator()
    controller = GenerationCycleController(
        generation_port=generator,
        grounding_port=_AlwaysLowGrounding(),
        value_port=PendingN8ValuePort(),
        repo_root=REPO_ROOT,
    )

    run = await controller.run(
        _problem(),
        budget_state=_budget(),
        min_cycles=2,
        max_cycles=3,
    )

    assert isinstance(run, GenerationCycleRun)
    assert [cycle.selected_candidate_ref for cycle in run.cycles[:2]] == [
        "candidate_cycle_1",
        "candidate_cycle_2",
    ]
    assert (
        run.cycles[1].selected_candidate_content_hash
        != run.cycles[0].selected_candidate_content_hash
    )
    assert (
        run.cycles[1].driven_by_counterexample_ref
        == run.cycles[0].counterexample.counterexample_ref
    )
    assert run.cycles[0].revision_request.revision_strategy == "adversarial_validate"
    assert run.cycles[0].revision_request.new_grammar_elements == (
        "lever:grant:adversarial_validate:missing_supporting_data",
    )
    assert run.cycles[1].introduced_grammar_elements == (
        "lever:grant:adversarial_validate:missing_supporting_data",
    )
    assert (
        generator.problems[1].runtime_hints["generation_cycle_revision"]["revision_strategy"]
        == "adversarial_validate"
    )
    assert run.cycles[1].revision_driver == "counterexample"
    assert run.cycles[0].voi_decision.next_action == "advance"
    assert run.terminal_status == "blocked"
    assert run.blocked_reason == "fake_cycle_same_candidate_repeated"
    assert run.cycles[-1].voi_decision.next_action == "advance"
    assert run.cycles[-1].voi_decision.reason == "voi_scheduler_advanced"
    assert run.cycles[-1].refinement_decision.decision == "block_candidate"
    assert run.cycles[-1].search_iteration.status == "blocked_no_retry"
    assert run.fronts.decision.candidate_ids == ()
    assert run.fronts.quarantine.candidate_ids == ("candidate_cycle_1",)
    assert run.fronts.research.candidate_ids == ("candidate_cycle_2",)
    assert run.fronts.portfolio.candidate_ids == ()
    assert run.value_port.status == "value_pending_n8"
    validation_codes = {
        issue.get("code")
        for issue in validate_generation_cycle_run(run, repo_root=REPO_ROOT)
    }
    # This hash-only repeat guard remains diagnostic, not producer-byte proof.
    assert "fake_cycle_same_candidate_repeated" in validation_codes


@pytest.mark.asyncio
async def test_blocked_voi_action_blocks_run_and_recursive_terminal(tmp_path: Path) -> None:
    class _BlockedActionController(GenerationCycleController):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.n7_route_checks = 0
            self.promotion_calls = 0

        def _promote_completed_generation(self, **kwargs: Any) -> Any:
            self.promotion_calls += 1
            return generation_cycle_module.PromotionPortObservation(
                status="not_promoted", reason="scratch_promotion_spy"
            )

        def decide_next_action(self, **kwargs: Any) -> Any:
            decision = super().decide_next_action(**kwargs)
            return decision.model_copy(
                update={"next_action": "blocked", "reason": "explicit_voi_block"}
            )

        def _plan_n7_requirement_gap_if_requested(
            self, problem: DesignProblem, *, cycle: Any
        ) -> None:
            del problem, cycle
            self.n7_route_checks += 1
            return None

    controller = _BlockedActionController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_AlwaysLowGrounding(),
        value_port=PendingN8ValuePort(),
        repo_root=tmp_path,
    )
    run = await controller.run(
        _problem(), budget_state=_budget(), min_cycles=2, max_cycles=3
    )

    assert run.terminal_status == "blocked"
    assert run.blocked_reason == "explicit_voi_block"
    assert len(run.cycles) == 1
    assert run.cycles[-1].voi_decision.next_action == "blocked"
    assert run.cycles[-1].voi_decision.reason == "explicit_voi_block"
    assert run.cycles[-1].refinement_decision.decision == "block_candidate"
    assert run.cycles[-1].search_iteration.status == "blocked_no_retry"
    assert controller.n7_route_checks == 0
    assert controller.promotion_calls == 0
    assert run.promotion_port.status == "not_promoted"
    assert run.promotion_port.reason == "generation_cycle_blocked_before_n9:explicit_voi_block"
    terminal = generation_cycle_terminal_state(run)
    assert terminal.kind.value == "recursive_blocked"
    assert terminal.blocking_obligations == ["explicit_voi_block"]

    removed_projection = run.model_copy(
        update={"terminal_status": "completed", "blocked_reason": None}
    )
    issues = generation_cycle_module._validate_generation_cycle_run(
        removed_projection, require_currentness=False
    )
    assert "voi_blocked_action_run_terminal_mismatch" in {
        issue.get("code") for issue in issues
    }
    assert generation_cycle_terminal_state(removed_projection).kind.value == "recursive_blocked"

    retained_promotion_marker = run.model_copy(
        update={
            "promotion_port": generation_cycle_module.PromotionPortObservation(
                status="certified_current_valid",
                certified_candidate_ids=("candidate_cycle_1",),
                receipts=({"marker": "retained_without_n9_owner"},),
            )
        }
    )
    promotion_issues = generation_cycle_module._validate_generation_cycle_run(
        retained_promotion_marker, require_currentness=False
    )
    assert "blocked_generation_cycle_n9_admission_mismatch" in {
        issue.get("code") for issue in promotion_issues
    }


@pytest.mark.asyncio
async def test_same_candidate_new_basis_preserves_history_and_current_front() -> None:
    """A changed basis is a new occurrence, not a second current-front row."""

    generator = _SameCandidateNewBasisGenerator()
    problem = _problem("same_subject_new_basis")
    run = await GenerationCycleController(
        generation_port=generator,
        grounding_port=_AlwaysLowGrounding(),
        value_port=PendingN8ValuePort(),
        repo_root=REPO_ROOT,
    ).run(
        problem,
        budget_state=_budget(),
        min_cycles=2,
        max_cycles=2,
    )

    assert len(run.candidate_summaries) == 2
    assert tuple(summary.candidate_id for summary in run.candidate_summaries) == (
        "candidate_same_subject",
        "candidate_same_subject",
    )
    assert tuple(summary.content_hash for summary in run.candidate_summaries) == (
        "sha256:" + "1" * 64,
        "sha256:" + "2" * 64,
    )
    assert len(
        {
            (summary.candidate_id, summary.content_hash, summary.cycle_index)
            for summary in run.candidate_summaries
        }
    ) == 2
    assert tuple(
        cycle.revision_request.revised_problem.design_problem_id for cycle in run.cycles
    ) == (problem.design_problem_id, problem.design_problem_id)
    assert run.cycles[0].design_problem_ref != run.cycles[1].design_problem_ref
    front_ids = tuple(
        candidate_id
        for candidate_ids in run.fronts.candidate_ids_by_front().values()
        for candidate_id in candidate_ids
    )
    assert front_ids == ("candidate_same_subject",)
    assert validate_generation_cycle_candidate_run(run) == ()
    strict_issue_codes = {
        issue["code"] for issue in validate_generation_cycle_run(run, repo_root=REPO_ROOT)
    }
    assert "strangle_receipt_currentness_not_established" in strict_issue_codes
    assert "single_pass_fixture_survives_as_production_cycle" not in strict_issue_codes




@pytest.mark.asyncio
async def test_blocked_n6_preempts_deployment_identity_mismatch_and_keeps_candidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blocked N6 run is terminal for N9 even when identity would also refuse."""

    current = confidence_ledger_module.capture_loaded_deployment_identity()
    assert current.status == "established"
    mismatched = "policy-engine-deployment:sha256:" + "f" * 64
    if mismatched == current.deployment_identity:
        mismatched = "policy-engine-deployment:sha256:" + "e" * 64
    monkeypatch.setattr(
        confidence_ledger_module,
        "capture_loaded_deployment_identity",
        lambda: LoadedDeploymentIdentityObservation(
            status="established",
            deployment_identity=mismatched,
        ),
    )
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    n9_preparation: list[bool] = []
    monkeypatch.setattr(
        runtime,
        "_prepare_completed_generation",
        lambda **_kwargs: n9_preparation.append(True),
    )

    run = await GenerationCycleController(
        generation_port=_SameCandidateNewBasisGenerator(),
        grounding_port=_AlwaysLowGrounding(),
        value_port=PendingN8ValuePort(),
        repo_root=REPO_ROOT,
        promotion_runtime=runtime,
    ).run(
        _problem("deployment_identity_mismatch"),
        budget_state=_budget(),
        min_cycles=2,
        max_cycles=2,
    )

    assert run.terminal_status == "blocked"
    assert run.blocked_reason == "voi_safety_cap_reached_without_scheduler_stop"
    assert run.cycles
    assert run.candidate_summaries
    assert run.deployment_identity_status == "established"
    assert run.deployment_identity == mismatched
    assert run.promotion_port.status == "not_promoted"
    assert run.promotion_port.reason == (
        "generation_cycle_blocked_before_n9:"
        "voi_safety_cap_reached_without_scheduler_stop"
    )
    assert run.promotion_port.receipts == ()
    assert n9_preparation == []
    assert generation_cycle_module.eligible_n9_source_for_run(run) is None


@pytest.mark.asyncio
async def test_nonblocked_candidate_source_preserves_canonical_identity_gate() -> None:
    class _SchedulerStopController(GenerationCycleController):
        def decide_next_action(self, **kwargs: Any) -> Any:
            decision = super().decide_next_action(**kwargs)
            return decision.model_copy(
                update={"next_action": "stop", "reason": "ordinary_scheduler_stop"}
            )

    problem = _problem("nonblocked_identity_gate_control")
    run = await _SchedulerStopController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_CurrentValidGrounding(),
        value_port=PendingN8ValuePort(),
        repo_root=REPO_ROOT,
    ).run(
        problem,
        budget_state=_budget(),
        min_cycles=2,
        max_cycles=3,
    )
    assert run.terminal_status == "completed"
    n9_source = generation_cycle_module.eligible_n9_source_for_run(run)
    assert n9_source is not None
    assert n9_source.run is run

    current = promotion_sequence_module.capture_loaded_deployment_identity()
    assert current.status == "established"
    assert current.deployment_identity is not None
    mismatched = "policy-engine-deployment:sha256:" + "f" * 64
    if mismatched == current.deployment_identity:
        mismatched = "policy-engine-deployment:sha256:" + "e" * 64
    port = CanonicalN9PromotionPort(repo_root=REPO_ROOT)
    refusal = port(
        admitted_batch=None,
        problem=problem,
        deployment_identity=mismatched,
    )
    assert refusal.reason == "confidence_ledger_refused:deployment_identity_mismatch"
    matching_identity_control = port(
        admitted_batch=None,
        problem=problem,
        deployment_identity=current.deployment_identity,
    )
    assert matching_identity_control.reason == (
        "epoch_validity_refused:promotion_runtime_not_established"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("loaded_identities", "expected_reason"),
    [
        (
            ("a" * 64, "b" * 64),
            "generation_cycle_n6_deployment_identity_stale:"
            "generation_cycle_deployment_identity_mismatch",
        ),
        (
            ("a" * 64, "a" * 64),
            "generation_cycle_n6_census_not_established:"
            "n6_census_issuer_not_appointed",
        ),
    ],
    ids=("identity-changes-before-n9", "same-identity-census-remains-unrun"),
)
async def test_pre_n9_rechecks_canonical_identity_without_refusing_candidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    loaded_identities: tuple[str, str],
    expected_reason: str,
) -> None:
    """The pre-N9 owner recheck blocks authority while retaining N6 candidates."""

    observations = iter(
        LoadedDeploymentIdentityObservation(
            status="established",
            deployment_identity=f"policy-engine-deployment:sha256:{identity}",
        )
        for identity in loaded_identities
    )
    capture_count = 0

    def capture_loaded_identity() -> LoadedDeploymentIdentityObservation:
        nonlocal capture_count
        capture_count += 1
        return next(observations)

    monkeypatch.setattr(
        confidence_ledger_module,
        "capture_loaded_deployment_identity",
        capture_loaded_identity,
    )
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    n9_preparation: list[bool] = []
    monkeypatch.setattr(
        runtime,
        "_prepare_completed_generation",
        lambda **_kwargs: n9_preparation.append(True),
    )

    class _SchedulerStopController(GenerationCycleController):
        def decide_next_action(self, **kwargs: Any) -> Any:
            decision = super().decide_next_action(**kwargs)
            return decision.model_copy(
                update={"next_action": "stop", "reason": "ordinary_scheduler_stop"}
            )

    run = await _SchedulerStopController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_CurrentValidGrounding(),
        value_port=PendingN8ValuePort(),
        repo_root=REPO_ROOT,
        promotion_runtime=runtime,
    ).run(
        _problem("pre_n9_identity_recheck"),
        budget_state=_budget(),
        min_cycles=2,
        max_cycles=3,
    )

    assert capture_count == 2
    assert run.terminal_status == "completed"
    assert run.candidate_summaries
    assert run.deployment_identity_status == "established"
    assert run.deployment_identity == (
        f"policy-engine-deployment:sha256:{loaded_identities[0]}"
    )
    assert run.promotion_port.status == "not_promoted"
    assert run.promotion_port.reason == expected_reason
    assert n9_preparation == []


@pytest.mark.asyncio
async def test_missing_deployment_identity_does_not_refuse_candidate_computation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown identity keeps N6 candidates but blocks real N9 before preparation."""

    monkeypatch.setattr(
        confidence_ledger_module,
        "capture_loaded_deployment_identity",
        lambda: LoadedDeploymentIdentityObservation(
            status="not_established",
            reason_code="canonical_loaded_runtime_mismatch",
        ),
    )

    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    n9_preparation: list[bool] = []
    monkeypatch.setattr(
        runtime,
        "_prepare_completed_generation",
        lambda **_kwargs: n9_preparation.append(True),
    )

    run = await GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        value_port=_DataGapValuePort(),
        repo_root=REPO_ROOT,
        promotion_runtime=runtime,
    ).run(_problem("candidate_with_unknown_deployment"), budget_state=_budget(), max_cycles=1)

    assert len(run.cycles) == 1
    assert run.deployment_identity_status == "not_established"
    assert run.deployment_identity is None
    assert run.deployment_identity_reason == "canonical_loaded_runtime_mismatch"
    currentness = generation_cycle_module.currentness_for_generation_cycle_run(run)
    assert currentness.reason_code == "historical_deployment_identity_not_recorded"
    assert currentness.loaded_identity_reason_code == "canonical_loaded_runtime_mismatch"
    assert run.promotion_port.status == "not_promoted"
    assert run.promotion_port.reason == (
        "generation_cycle_n6_census_not_established:loaded_deployment_identity_not_established"
    )
    assert n9_preparation == []

    unprovided_identity_payload = run.model_dump(mode="json")
    unprovided_identity_payload.pop("deployment_identity_status")
    unprovided_identity_payload.pop("deployment_identity")
    unprovided_identity_payload.pop("deployment_identity_reason")
    defaulted_run = GenerationCycleRun.model_validate(unprovided_identity_payload)
    assert defaulted_run.deployment_identity_status == "not_established"
    assert defaulted_run.deployment_identity is None
    assert defaulted_run.deployment_identity_reason == "loaded_deployment_identity_not_supplied"


@pytest.mark.asyncio
async def test_blocked_run_preserves_current_occurrence_and_basis_without_n9(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The current N6 occurrence survives a terminal block without entering N9."""

    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    n9_preparation: list[bool] = []
    monkeypatch.setattr(
        runtime,
        "_prepare_completed_generation",
        lambda **_kwargs: n9_preparation.append(True),
    )
    run = await GenerationCycleController(
        generation_port=_SameCandidateNewBasisGenerator(),
        grounding_port=_AlwaysLowGrounding(),
        value_port=PendingN8ValuePort(),
        repo_root=REPO_ROOT,
        promotion_runtime=runtime,
    ).run(
        _problem("same_subject_owner_basis"),
        budget_state=_budget(),
        min_cycles=2,
        max_cycles=2,
    )

    assert run.terminal_status == "blocked"
    assert run.blocked_reason == "voi_safety_cap_reached_without_scheduler_stop"
    assert len(run.cycles) == 2
    assert run.cycles[0].design_problem_ref != run.cycles[1].design_problem_ref
    assert run.cycles[-1].design_problem_basis_ref == run.cycles[-1].design_problem_ref
    assert tuple(summary.content_hash for summary in run.candidate_summaries) == (
        "sha256:" + "1" * 64,
        "sha256:" + "2" * 64,
    )
    front_ids = tuple(
        candidate_id
        for candidate_ids in run.fronts.candidate_ids_by_front().values()
        for candidate_id in candidate_ids
    )
    assert front_ids == ("candidate_same_subject",)
    assert n9_preparation == []
    assert run.promotion_port.reason == (
        "generation_cycle_blocked_before_n9:"
        "voi_safety_cap_reached_without_scheduler_stop"
    )
    assert generation_cycle_module.eligible_n9_source_for_run(run) is None


@pytest.mark.asyncio
async def test_nonblocked_latest_occurrence_reaches_runtime_or_types_currentness_unrun(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep ordinary N6 work visible and pass its latest basis when currentness permits."""

    generator = _SameCandidateNewBasisGenerator()
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    observed: dict[str, object] = {}
    prepare = runtime._prepare_completed_generation

    def capture_prepare(*, problem: DesignProblem, summaries: Any) -> Any:
        observed["problem"] = problem
        observed["summaries"] = tuple(summaries)
        return prepare(problem=problem, summaries=summaries)

    monkeypatch.setattr(runtime, "_prepare_completed_generation", capture_prepare)

    class _CurrentValidOnSecondCycleGrounding:
        def __init__(self) -> None:
            self._initial_gap = _AlwaysLowGrounding()
            self._current_grounding = _CurrentValidGrounding()

        def __call__(
            self,
            *,
            candidate: Any,
            problem: DesignProblem,
            cycle_index: int,
            generation_result: Any | None = None,
        ) -> CandidateGroundingObservation:
            grounding = (
                self._initial_gap if cycle_index == 0 else self._current_grounding
            )
            return grounding(
                candidate=candidate,
                problem=problem,
                cycle_index=cycle_index,
                generation_result=generation_result,
            )

    problem = _problem("same_subject_owner_basis_nonblocked_control")
    run = await GenerationCycleController(
        generation_port=generator,
        grounding_port=_CurrentValidOnSecondCycleGrounding(),
        value_port=_ReadyValuePort(),
        repo_root=REPO_ROOT,
        promotion_runtime=runtime,
    ).run(
        problem,
        budget_state=_budget(),
        min_cycles=2,
        max_cycles=3,
    )

    assert run.terminal_status == "completed"
    assert run.blocked_reason is None
    assert len(run.cycles) == 2
    assert run.cycles[0].terminal_kind == "search_ceiling_repair_required"
    assert run.cycles[0].voi_decision.next_action == "advance"
    assert run.cycles[0].voi_decision.reason == "voi_scheduler_advanced"
    assert run.cycles[-1].terminal_kind == "grounded_admissible"
    assert run.cycles[-1].voi_decision.next_action == "stop"
    assert run.cycles[-1].voi_decision.reason == (
        "terminal_stops_loop:grounded_admissible"
    )
    assert run.cycles[0].design_problem_ref != run.cycles[-1].design_problem_ref
    assert gy_content_hash(generator.problems[-1].model_dump(mode="json")) == (
        run.cycles[-1].design_problem_basis_ref
    )
    assert tuple(summary.content_hash for summary in run.candidate_summaries) == (
        "sha256:" + "1" * 64,
        "sha256:" + "2" * 64,
    )
    front_ids = tuple(
        candidate_id
        for candidate_ids in run.fronts.candidate_ids_by_front().values()
        for candidate_id in candidate_ids
    )
    assert front_ids == ("candidate_same_subject",)

    currentness = confidence_ledger_module.observe_n6_deployment_currentness(
        recorded_identity_status=run.deployment_identity_status,
        recorded_deployment_identity=run.deployment_identity,
    )
    unrun_reason = (
        "generation_cycle_n6_census_not_established:"
        "n6_census_issuer_not_appointed"
    )
    if run.promotion_port.reason != unrun_reason:
        assert currentness.status == "current"
        assert currentness.census_verdict == "PASS"
        assert run.promotion_port.status == "not_promoted"
        assert run.promotion_port.reason == "epoch_validity_refused:policy_admission_missing"
        owner_summaries = observed.get("summaries")
        assert isinstance(owner_summaries, tuple)
        assert len(owner_summaries) == 1
        assert owner_summaries[0].candidate_id == "candidate_same_subject"
        assert owner_summaries[0].content_hash == "sha256:" + "2" * 64
        owner_problem = observed.get("problem")
        assert isinstance(owner_problem, DesignProblem)
        assert owner_problem == generator.problems[-1]
        assert gy_content_hash(owner_problem.model_dump(mode="json")) == (
            run.cycles[-1].design_problem_basis_ref
        )
    else:
        assert currentness.status == "not_established"
        assert currentness.census_verdict == "UNRUN"
        assert currentness.reason_code == "n6_census_issuer_not_appointed"
        assert run.strangle_receipt.status == "not_established"
        assert "n6_census_issuer_not_appointed" in run.strangle_receipt.limitation_refs
        assert run.promotion_port.status == "not_promoted"
        assert run.promotion_port.reason == unrun_reason
        assert observed == {}


def test_changed_population_and_model_rebind_owner_basis_and_occurrence(
    tmp_path: Path,
) -> None:
    """A population/model change must not reuse the prior promotion basis."""

    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    problem = _problem("changed_basis_owner")
    summary = _open_world_summary("changed_basis_candidate")
    original = runtime._prepare_completed_generation(problem=problem, summaries=(summary,))
    assert hasattr(original, "contexts")

    changed_problem = problem.model_copy(
        update={
            "model_spec_ref": "sha256:" + "9" * 64,
            "stakeholders": [
                DesignStakeholder(
                    stakeholder_id="large_firms",
                    name="Large firms",
                    role="target_population",
                )
            ],
        }
    )
    changed = runtime._prepare_completed_generation(
        problem=changed_problem,
        summaries=(summary,),
    )
    assert hasattr(changed, "contexts")

    original_statement = original.contexts.aggregate_context.statement
    changed_statement = changed.contexts.aggregate_context.statement
    assert (
        original_statement.design_problem_binding_ref
        != changed_statement.design_problem_binding_ref
    )
    assert (
        original_statement.design_problem_binding_content_hash
        != changed_statement.design_problem_binding_content_hash
    )
    original_occurrence = original.contexts.ordered_bound_members[0].statement
    changed_occurrence = changed.contexts.ordered_bound_members[0].statement
    assert (
        original_occurrence.candidate_occurrence_ref
        != changed_occurrence.candidate_occurrence_ref
    )
    original_occurrence_record = runtime.context_repository.resolve_occurrence(
        occurrence_ref=original_occurrence.candidate_occurrence_ref
    )
    changed_occurrence_record = runtime.context_repository.resolve_occurrence(
        occurrence_ref=changed_occurrence.candidate_occurrence_ref
    )
    assert (
        core_contracts.c4_semantic_digest("candidate_occurrence", original_occurrence_record)
        != core_contracts.c4_semantic_digest("candidate_occurrence", changed_occurrence_record)
    )


def test_no_retry_without_new_grammar_blocks_same_candidate_retry() -> None:
    with pytest.raises(GenerationCycleError, match="no_retry_without_new_grammar"):
        enforce_no_retry_without_new_grammar(
            previous_candidate_ref="candidate_cycle_1",
            next_candidate_ref="candidate_cycle_1",
            previous_grammar_elements=("seed",),
            next_grammar_elements=("seed",),
            introduced_grammar_elements=(),
            design_problem=_problem(),
        )


def test_no_retry_without_new_grammar_rejects_laundered_revision_claim() -> None:
    with pytest.raises(GenerationCycleError, match="new_grammar_elements_not_introduced"):
        enforce_no_retry_without_new_grammar(
            previous_candidate_ref="candidate_cycle_1",
            next_candidate_ref="candidate_cycle_2",
            previous_grammar_elements=("seed",),
            next_grammar_elements=("seed",),
            introduced_grammar_elements=("fabricated_new_axis",),
            design_problem=_problem(),
        )


def test_no_retry_without_new_grammar_rejects_fabricated_owned_by_caller_only() -> None:
    with pytest.raises(GenerationCycleError, match="new_grammar_element_not_owned"):
        enforce_no_retry_without_new_grammar(
            previous_candidate_ref="candidate_a",
            next_candidate_ref="candidate_b",
            previous_grammar_elements=("seed",),
            next_grammar_elements=("seed", "fabricated:not_from_s2_owner"),
            introduced_grammar_elements=("fabricated:not_from_s2_owner",),
            design_problem=_problem(),
        )

    with pytest.raises(GenerationCycleError, match="new_grammar_owner_missing"):
        enforce_no_retry_without_new_grammar(
            previous_candidate_ref="candidate_a",
            next_candidate_ref="candidate_b",
            previous_grammar_elements=("seed",),
            next_grammar_elements=("seed", "fabricated:not_from_s2_owner"),
            introduced_grammar_elements=("fabricated:not_from_s2_owner",),
        )


@pytest.mark.asyncio
async def test_controller_refuses_live_retry_without_new_grammar() -> None:
    controller = GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_AlwaysLowGrounding(),
        value_port=PendingN8ValuePort(),
        revision_policy=_NoNewGrammarRevision(),
    )

    run = await controller.run(
        _problem(),
        budget_state=_budget(),
        min_cycles=2,
        max_cycles=3,
    )

    assert run.terminal_status == "blocked"
    assert run.blocked_reason == "no_retry_without_new_grammar"
    assert run.cycles[0].voi_decision.next_action == "advance"
    assert run.cycles[0].voi_decision.reason == "voi_scheduler_advanced"
    assert run.cycles[0].refinement_decision.decision == "block_candidate"
    assert run.cycles[0].refinement_decision.reason == "no_retry_without_new_grammar"
    assert run.cycles[0].search_iteration.status == "blocked_no_retry"
    guard_issues = generation_cycle_module._validate_generation_cycle_run(
        run, require_currentness=False
    )
    assert "generation_cycle_block_cause_not_reconciled" not in {
        issue.get("code") for issue in guard_issues
    }
    terminal = generation_cycle_terminal_state(run)
    assert terminal.kind.value == "recursive_blocked"
    assert terminal.blocking_obligations == ["no_retry_without_new_grammar"]


@pytest.mark.parametrize(
    ("block_path", "expected_reason", "max_cycles"),
    [
        ("retry_guard", "no_retry_without_new_grammar", 3),
        (
            "cycle_safety_cap",
            "voi_safety_cap_reached_without_scheduler_stop",
            1,
        ),
    ],
)
@pytest.mark.asyncio
async def test_guard_or_safety_cap_block_skips_n9_for_current_valid_candidate(
    block_path: str,
    expected_reason: str,
    max_cycles: int,
) -> None:
    class _PromotionSpyController(GenerationCycleController):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.promotion_calls = 0

        def decide_next_action(self, **kwargs: Any) -> Any:
            decision = super().decide_next_action(**kwargs)
            # Isolate the guard/cap boundary with the same candidate-bearing action.
            return decision.model_copy(
                update={"next_action": "advance", "reason": "voi_scheduler_advanced"}
            )

        def _promote_completed_generation(self, **kwargs: Any) -> Any:
            self.promotion_calls += 1
            return generation_cycle_module.PromotionPortObservation(
                status="not_promoted", reason="scratch_promotion_spy"
            )

    controller = _PromotionSpyController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_CurrentValidRepairGrounding(),
        value_port=PendingN8ValuePort(),
        revision_policy=(
            _NoNewGrammarRevision() if block_path == "retry_guard" else None
        ),
    )
    run = await controller.run(
        _problem(f"blocked_valid_candidate_{block_path}"),
        budget_state=_budget(),
        max_cycles=max_cycles,
    )

    assert run.terminal_status == "blocked"
    assert run.blocked_reason == expected_reason
    assert len(run.cycles) == 1
    assert run.cycles[0].grounding.current_valid is True
    assert run.cycles[0].voi_decision.next_action == "advance"
    assert run.cycles[0].voi_decision.reason == "voi_scheduler_advanced"
    assert controller.promotion_calls == 0
    assert run.promotion_port.status == "not_promoted"
    assert run.promotion_port.reason == (
        f"generation_cycle_blocked_before_n9:{expected_reason}"
    )
    issues = generation_cycle_module._validate_generation_cycle_run(
        run, require_currentness=False
    )
    assert "blocked_generation_cycle_n9_admission_mismatch" not in {
        issue.get("code") for issue in issues
    }

    forged_promotion = run.model_copy(
        update={
            "promotion_port": generation_cycle_module.PromotionPortObservation(
                status="certified_current_valid",
                certified_candidate_ids=(run.cycles[0].selected_candidate_ref,),
                receipts=({"marker": "retained_without_n9_owner"},),
            )
        }
    )
    forged_issues = generation_cycle_module._validate_generation_cycle_run(
        forged_promotion, require_currentness=False
    )
    assert "blocked_generation_cycle_n9_admission_mismatch" in {
        issue.get("code") for issue in forged_issues
    }


@pytest.mark.asyncio
async def test_uuid_and_timestamp_only_revision_is_blocked_as_no_progress() -> None:
    """Fresh technical identifiers do not launder an unchanged research basis."""

    class _IdentifierOnlyRevision:
        def __call__(self, **kwargs: Any) -> Any:
            prior_cycle = kwargs["prior_cycle"]
            problem = kwargs["problem"]
            default = kwargs["default_revision"]
            revised_problem = problem.model_copy(
                update={
                    "runtime_hints": {
                        **problem.runtime_hints,
                        "research_attempt_uuid": uuid4().hex,
                        "research_attempt_at": "2026-09-21T00:00:00Z",
                    }
                }
            )
            return default.model_copy(
                update={
                    "next_candidate_ref": f"candidate://technical-retry/{uuid4().hex}",
                    "new_grammar_elements": (),
                    "next_grammar_elements": prior_cycle.revision_request.previous_grammar_elements,
                    "revised_problem": revised_problem,
                }
            )

    run = await GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_AlwaysLowGrounding(),
        value_port=PendingN8ValuePort(),
        revision_policy=_IdentifierOnlyRevision(),
    ).run(
        _problem("technical_identifier_retry"),
        budget_state=_budget(),
        min_cycles=2,
        max_cycles=3,
    )

    assert run.terminal_status == "blocked"
    assert run.blocked_reason == "no_retry_without_new_grammar"
    assert len(run.cycles) == 1


@pytest.mark.asyncio
async def test_revision_changes_when_prior_terminal_changes() -> None:
    search_controller = GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_AlwaysLowGrounding(),
        value_port=PendingN8ValuePort(),
    )
    acquisition_controller = GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_AcquisitionGrounding(),
        value_port=PendingN8ValuePort(),
    )

    search_run = await search_controller.run(_problem(), budget_state=_budget(), max_cycles=1)
    acquisition_run = await acquisition_controller.run(
        _problem(), budget_state=_budget(), max_cycles=1
    )

    assert search_run.cycles[0].terminal_kind == "search_ceiling_repair_required"
    assert acquisition_run.cycles[0].terminal_kind == "acquisition_required"
    assert search_run.cycles[0].revision_request.revision_strategy == "adversarial_validate"
    assert acquisition_run.cycles[0].revision_request.revision_strategy == "acquire_or_elicit"
    assert (
        search_run.cycles[0].revision_request.revision_strategy
        != acquisition_run.cycles[0].revision_request.revision_strategy
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("route_marker", [None, "route-marker", ["not", "a", "route"]])
async def test_production_n7_route_less_claim_cannot_reenter_n5(route_marker, monkeypatch) -> None:
    """Route-less growth markers cannot replace native admission evidence."""

    data_spec = _n7_data_requirement_spec()
    problem = _problem().model_copy(
        update={
            "runtime_hints": {
                "n7_data_requirement_specs": (data_spec,),
                "n7_world_snapshot": AcquisitionWorldSnapshot(
                    world_ref="world://before/n6-n7-nonroute",
                    known_slots=("owner_panel_missing",),
                    dependency_index={"owner_panel_missing": ("candidate_cycle_1",)},
                    design_revalidation_stages={
                        "candidate_cycle_1": (
                            "identification",
                            "calibration",
                            "value_set",
                            "grounding",
                        )
                    },
                    substrate_registry=_n7_substrate_registry().model_dump(mode="json"),
                ),
                "n7_useful_design_rate_before": 0.0,
            }
        }
    )
    atom = _canonical_n7_test_atom(
        problem,
        candidate_id="candidate_cycle_1",
        target_world_slot="owner_panel_missing",
    )
    payload = _n7_owner_payload(
        acquired_family="owner_panel_missing",
        source_id="fabric.owner_panel_missing",
        candidate_id="candidate_cycle_1",
        candidate_content_hash=atom.content_hash,
        target_world_slots=atom.target_world_slots,
    )
    payload["acq01_route"] = route_marker
    artifact = AcquisitionOwnerArtifact.from_payload(
        owner_component="fabric.ingestion",
        requirement_ref=data_spec.requirement_id,
        artifact_ref="fabric://recorded/owner-panel-missing/nonroute",
        payload=payload,
        cost_usd=2.0,
        quality={"capture": "real_owner_recording"},
        rights={"license": "recorded-open"},
        binding_refs=("candidate_cycle_1",),
        journal_ref="journal://n7/owner-panel-missing/nonroute",
        capture_provenance=AcquisitionCaptureProvenance.from_owner_response(
            owner_component="fabric.ingestion",
            owner_endpoint="fabric.ingestion.acquire",
            owner_request={"requirement_ref": data_spec.requirement_id},
            owner_response=payload,
            captured_at=datetime(2026, 7, 5, tzinfo=UTC),
            capture_mode="local_substrate_owner",
        ),
    )
    assert artifact.payload["acq01_route"] == route_marker
    assert artifact.payload["acquired_substrate_registrations"]

    emitted_local_receipts = []
    original_acquisition = generation_cycle_module.run_acquisition_closed_loop

    def capture_local_receipt(*args, **kwargs):
        receipt = original_acquisition(*args, **kwargs)
        emitted_local_receipts.append(receipt)
        return receipt

    n5_calls = 0
    original_joint_value_node = GenerationCycleController._joint_value_node

    def count_joint_value_node(self, state):
        nonlocal n5_calls
        if self._authority_scope == "production":
            n5_calls += 1
        return original_joint_value_node(self, state)

    monkeypatch.setattr(generation_cycle_module, "run_acquisition_closed_loop", capture_local_receipt)
    monkeypatch.setattr(GenerationCycleController, "_joint_value_node", count_joint_value_node)
    controller = GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(first_atom=atom),
        grounding_port=_AcquisitionGrounding(),
        value_port=PendingN8ValuePort(),
        acquisition_owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={data_spec.requirement_id: artifact}
        ),
        repo_root=Path(__file__).resolve().parents[4],
        authority_scope="production",
    )

    run = await controller.run(problem, budget_state=_budget(), max_cycles=1)

    cycle = run.cycles[0]
    assert len(emitted_local_receipts) == 1
    local_receipt = emitted_local_receipts[0]
    assert local_receipt.owner_artifacts[0].payload["acq01_route"] == route_marker
    assert local_receipt.owner_artifacts[0].payload["acquired_substrate_registrations"]
    assert local_receipt.grown_world_after_ref
    assert "same_cycle_reentry" in local_receipt.authority_boundary["authoritative_for"]
    assert "affected_region_revalidation" in local_receipt.authority_boundary["authoritative_for"]
    assert n5_calls == 1  # initial N5 only; the unadmitted local WMR is never consumed
    assert cycle.acquisition_receipt is None
    assert cycle.terminal_kind == "acquisition_required"
    assert cycle.voi_decision.next_action == "escalate"
    assert cycle.search_iteration.status == "acquisition_required"
    assert cycle.counterexample.diagnostic.code == (
        "n6.acquisition.n7_runtime_store_not_supplied"
    )


@pytest.mark.asyncio
async def test_default_production_n7_without_runtime_store_keeps_typed_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing owner storage limits N7 while preserving the candidate."""

    data_spec = _n7_data_requirement_spec()
    problem = _problem("production_n7_without_runtime_store").model_copy(
        update={
            "runtime_hints": {
                "n7_data_requirement_specs": (data_spec,),
                "n7_world_snapshot": AcquisitionWorldSnapshot(
                    world_ref="world://production-n7-without-runtime-store",
                    known_slots=("owner_panel_missing",),
                    dependency_index={"owner_panel_missing": ("candidate_cycle_1",)},
                    design_revalidation_stages={
                        "candidate_cycle_1": (
                            "identification",
                            "calibration",
                            "value_set",
                            "grounding",
                        )
                    },
                    substrate_registry=_n7_substrate_registry().model_dump(mode="json"),
                ),
                "n7_useful_design_rate_before": 0.0,
            }
        }
    )
    atom = _canonical_n7_test_atom(
        problem,
        candidate_id="candidate_cycle_1",
        target_world_slot="owner_panel_missing",
    )
    acquisition_calls = 0
    original_acquisition = generation_cycle_module.run_acquisition_closed_loop

    def count_acquisition(*args, **kwargs):
        nonlocal acquisition_calls
        acquisition_calls += 1
        return original_acquisition(*args, **kwargs)

    monkeypatch.setattr(
        generation_cycle_module,
        "run_acquisition_closed_loop",
        count_acquisition,
    )
    controller = GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(first_atom=atom),
        grounding_port=_AcquisitionGrounding(),
        value_port=PendingN8ValuePort(),
        repo_root=tmp_path,
        authority_scope="production",
    )

    assert controller._n7_owner_gateway(problem) is None
    run = await controller.run(problem, budget_state=_budget(), max_cycles=1)

    cycle = run.cycles[0]
    assert acquisition_calls == 0
    assert cycle.terminal_kind == "acquisition_required"
    assert cycle.candidate_ids
    assert cycle.counterexample.diagnostic.code == (
        "n6.acquisition.n7_runtime_store_not_supplied"
    )
    assert not (tmp_path / ".n7-live-cas").exists()


@pytest.mark.asyncio
async def test_production_candidate_without_n7_receipt_is_not_refused() -> None:
    """The admission boundary limits world growth, not ordinary candidate work."""

    controller = GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_StableShadowGrounding(),
        value_port=_ReadyValuePort(),
        authority_scope="production",
    )

    run = await controller.run(
        _problem("production_candidate_control"),
        budget_state=_budget(),
        max_cycles=1,
    )

    assert run.cycles
    assert run.cycles[0].candidate_ids
    assert run.terminal_status != "blocked"
    assert run.cycles[0].terminal_kind == "frontier_stable"
    assert run.cycles[0].counterexample.diagnostic.code != (
        "n6.acquisition.n7_native_admission_not_established"
    )


@pytest.mark.asyncio
async def test_acquisition_required_invokes_n7_and_records_same_cycle_reentry() -> None:
    data_spec = _n7_data_requirement_spec()
    problem = _problem().model_copy(
        update={
            "runtime_hints": {
                "n7_data_requirement_specs": (data_spec,),
                "n7_world_snapshot": AcquisitionWorldSnapshot(
                    world_ref="world://before/n6-n7",
                    known_slots=("owner_panel_missing",),
                    dependency_index={"owner_panel_missing": ("candidate_cycle_1",)},
                    design_revalidation_stages={
                        "candidate_cycle_1": (
                            "identification",
                            "calibration",
                            "value_set",
                            "grounding",
                        )
                    },
                    substrate_registry=_n7_substrate_registry().model_dump(mode="json"),
                ),
                "n7_useful_design_rate_before": 0.0,
            }
        }
    )
    atom = _canonical_n7_test_atom(
        problem,
        candidate_id="candidate_cycle_1",
        target_world_slot="owner_panel_missing",
    )
    payload = _n7_owner_payload(
        acquired_family="owner_panel_missing",
        source_id="fabric.owner_panel_missing",
        candidate_id="candidate_cycle_1",
        candidate_content_hash=atom.content_hash,
        target_world_slots=atom.target_world_slots,
    )
    artifact = AcquisitionOwnerArtifact.from_payload(
        owner_component="fabric.ingestion",
        requirement_ref=data_spec.requirement_id,
        artifact_ref="fabric://recorded/owner-panel-missing",
        payload=payload,
        cost_usd=2.0,
        quality={"capture": "real_owner_recording"},
        rights={"license": "recorded-open"},
        binding_refs=("candidate_cycle_1",),
        journal_ref="journal://n7/owner-panel-missing/001",
        capture_provenance=AcquisitionCaptureProvenance.from_owner_response(
            owner_component="fabric.ingestion",
            owner_endpoint="fabric.ingestion.acquire",
            owner_request={"requirement_ref": data_spec.requirement_id},
            owner_response=payload,
            captured_at=datetime(2026, 7, 5, tzinfo=UTC),
            capture_mode="local_substrate_owner",
        ),
    )
    controller = GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(first_atom=atom),
        grounding_port=_AcquisitionGrounding(),
        value_port=PendingN8ValuePort(),
        acquisition_owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={data_spec.requirement_id: artifact}
        ),
        authority_scope="contract_testing",
    )

    run = await controller.run(problem, budget_state=_budget(), max_cycles=1)

    assert run.cycles[0].acquisition_receipt is not None
    receipt = run.cycles[0].acquisition_receipt
    assert receipt["source_cycle_index"] == 0
    assert receipt["reentry_cycle_index"] == 0
    assert receipt["real_grounding_result_count"] == 1
    assert receipt["useful_design_rate_after"] > 0.0
    assert run.cycles[0].terminal_kind == "grounded_abstention"
    assert run.cycles[0].grounding.status == "grounded_shadow"
    assert run.candidate_summaries[0].grounding_status == "grounded_shadow"
    assert run.acquisition_receipts == (receipt,)


@pytest.mark.asyncio
@_requires_owner_catalog
async def test_acquisition_required_derives_n7_inputs_without_test_hints_and_reenters() -> None:
    compiled = compile_data_requirements_for_scenario(
        {
            "scenario_id": "generic_cycle_problem",
            "text": "Acquire owner_panel_missing to ground the blocked candidate.",
            "domain": "generic_policy",
            "expected_evidence_contract": {
                "admissible_data_source_families": ["owner_panel_missing"]
            },
        }
    )
    data_spec = compiled.specs[0]
    problem = _problem()
    atom = _canonical_n7_test_atom(
        problem,
        candidate_id="candidate_cycle_1",
        target_world_slot="owner_panel_missing",
    )
    payload = _n7_owner_payload(
        acquired_family="owner_panel_missing",
        source_id="fabric.owner_panel_missing",
        candidate_id="candidate_cycle_1",
        candidate_content_hash=atom.content_hash,
        target_world_slots=atom.target_world_slots,
    )
    artifact = AcquisitionOwnerArtifact.from_payload(
        owner_component="fabric.ingestion",
        requirement_ref=data_spec.requirement_id,
        artifact_ref="fabric://recorded/owner-panel-missing",
        payload=payload,
        cost_usd=2.0,
        quality={"capture": "recorded-owner"},
        rights={"license": "recorded-open"},
        binding_refs=("candidate_cycle_1",),
        journal_ref="journal://n7/owner-panel-missing/production-default",
        capture_provenance=AcquisitionCaptureProvenance.from_owner_response(
            owner_component="fabric.ingestion",
            owner_endpoint="fabric.ingestion.acquire",
            owner_request={"requirement_ref": data_spec.requirement_id},
            owner_response=payload,
            captured_at=datetime(2026, 7, 5, tzinfo=UTC),
            capture_mode="local_substrate_owner",
        ),
    )
    assert not any(key.startswith("n7_") for key in problem.runtime_hints)
    controller = GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(first_atom=atom),
        grounding_port=_AcquisitionGrounding(),
        value_port=PendingN8ValuePort(),
        acquisition_owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={data_spec.requirement_id: artifact}
        ),
        authority_scope="contract_testing",
    )

    run = await controller.run(problem, budget_state=_budget(), max_cycles=1)

    cycle = run.cycles[0]
    assert cycle.acquisition_receipt is not None
    assert cycle.acquisition_receipt["real_grounding_result_count"] == 1
    assert cycle.terminal_kind != "acquisition_required"
    assert cycle.terminal_kind == "grounded_abstention"
    assert cycle.grounding.status == "grounded_shadow"
    assert cycle.grounding.report_ref
    assert run.candidate_summaries[0].grounding_status == "grounded_shadow"
    assert run.candidate_summaries[0].front == "research"


@pytest.mark.asyncio
async def test_constant_strategy_revision_is_rejected_as_not_terminal_driven() -> None:
    controller = GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_AcquisitionGrounding(),
        value_port=PendingN8ValuePort(),
        revision_policy=_ConstantStrategyRevision(),
    )

    run = await controller.run(_problem(), budget_state=_budget(), max_cycles=1)

    assert any(
        issue["code"] == "revision_not_terminal_driven"
        for issue in validate_generation_cycle_run(run)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("grounding_port", "value_port", "expected_terminal", "expected_decision"),
    [
        (
            _StableShadowGrounding,
            _ReadyValuePort,
            "frontier_stable",
            "stop",
        ),
        (
            _CurrentValidGrounding,
            _ReadyValuePort,
            "grounded_admissible",
            "stop",
        ),
        (
            _StableShadowGrounding,
            _BudgetExhaustedValuePort,
            "budget_exhausted",
            "stop",
        ),
        (
            _StableShadowGrounding,
            PendingN8ValuePort,
            "grounded_abstention",
            "abstain",
        ),
    ],
    ids=("frontier-stable", "grounded-admissible", "budget-stop", "abstention"),
)
async def test_terminal_projection_preserves_stop_budget_and_abstention(
    grounding_port: type[Any],
    value_port: type[Any],
    expected_terminal: str,
    expected_decision: str,
) -> None:
    """N6 records keep controller stop distinct from epistemic abstention."""

    run = await GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=grounding_port(),
        value_port=value_port(),
    ).run(
        _problem(f"b29_{expected_terminal}"),
        budget_state=_budget(),
        max_cycles=1,
    )

    cycle = run.cycles[0]
    assert cycle.terminal_kind == expected_terminal
    assert cycle.voi_decision.next_action == "stop"
    assert cycle.refinement_decision.decision == expected_decision
    assert cycle.search_iteration.status == (
        "abstained" if expected_decision == "abstain" else "stopped"
    )


@pytest.mark.asyncio
async def test_voi_scheduler_changes_next_action_under_varying_budget_and_terminal() -> None:
    controller = GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_AlwaysLowGrounding(),
        value_port=PendingN8ValuePort(),
    )

    advance = controller.decide_next_action(
        candidate_id="candidate_advance",
        proxy_score=0.8,
        voi_estimate=0.8,
        prior_terminal_kind="search_ceiling_repair_required",
        budget_state=_budget("5.0"),
    )
    stop = controller.decide_next_action(
        candidate_id="candidate_stop",
        proxy_score=0.2,
        voi_estimate=0.0,
        prior_terminal_kind="frontier_stable",
        budget_state=_budget("5.0"),
    )
    escalate = controller.decide_next_action(
        candidate_id="candidate_escalate",
        proxy_score=0.8,
        voi_estimate=0.8,
        prior_terminal_kind="acquisition_required",
        budget_state=_budget("5.0"),
    )

    assert advance.next_action == "advance"
    assert stop.next_action == "stop"
    assert escalate.next_action == "escalate"
    assert {advance.scheduler_action, stop.scheduler_action, escalate.terminal_kind} >= {
        "advance",
        "reject",
        "acquisition_required",
    }


@pytest.mark.asyncio
async def test_empty_llm_generation_uses_grammar_fallback_without_promotion() -> None:
    controller = GenerationCycleController(
        generation_port=_EmptyGenerationPort(),
        grounding_port=_AlwaysLowGrounding(),
        value_port=PendingN8ValuePort(),
    )

    run = await controller.run(_problem(), budget_state=_budget(), max_cycles=1)

    assert run.candidate_summaries
    assert {summary.generation_channel for summary in run.candidate_summaries} == {
        "grammar_fallback"
    }
    assert run.fronts.decision.candidate_ids == ()


@pytest.mark.asyncio
async def test_n4_port_without_owner_context_refuses_before_scientist_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A no-pack cycle cannot borrow the fixed Scientist vertical vocabulary."""

    from polisyos.runtime.quality import design_generation

    calls = 0

    async def _forbidden_generation(*args: Any, **kwargs: Any) -> object:
        nonlocal calls
        del args, kwargs
        calls += 1
        raise AssertionError("scientist_generation_reached_without_owner_context")

    monkeypatch.setattr(
        design_generation,
        "generate_design_candidate_bundle_under_a",
        _forbidden_generation,
    )
    port = N4GenerationPort(
        model_id="owner-selected-model",
        repo_root=REPO_ROOT,
        cycle_substrate_context=None,
    )

    result = await port(_problem(), cycle_index=0)

    assert calls == 0
    assert result.status == "cycle_substrate_context_unavailable"
    assert result.candidates == ()


@pytest.mark.asyncio
async def test_default_grounding_port_rejects_legacy_matrix_without_cgf_disposition() -> None:
    controller = GenerationCycleController(
        generation_port=_LegacyOnlyGenerationPort(),
        grounding_port=PolicyGroundingPort(),
        value_port=PendingN8ValuePort(),
    )

    run = await controller.run(_problem(), budget_state=_budget(), max_cycles=1)

    assert run.cycles[0].grounding.status == "grounding_unavailable"
    assert "cgf_disposition_missing" in run.cycles[0].grounding.issue_codes
    assert run.fronts.decision.candidate_ids == ()


def test_default_grounding_port_resolves_real_serialized_n4_candidate() -> None:
    result, candidate = _real_n4_generation_result_with_candidate()
    problem = _recorded_problem_for_candidate(candidate)
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    assert result["design_problem_ref"] == problem_ref
    assert candidate["atom"]["problem_frame_ref"] == problem_ref

    grounding = PolicyGroundingPort()(
        candidate=candidate,
        problem=problem,
        cycle_index=0,
        generation_result=result,
    )

    assert grounding.candidate_id == candidate["candidate_id"]
    assert grounding.status == "grounded_shadow"
    assert grounding.current_valid is False
    assert "cgf_disposition_missing" not in grounding.issue_codes
    assert grounding.grounding_source == "cgf_firewall"
    assert grounding.grounding_disposition in {
        "shadow_bound",
        "novel_cg3",
        "non_binding_abstain",
        "veto_false_analog",
        "unknown_blocked",
    }


def test_grounding_port_rejects_foreign_basis_with_candidate_only_control() -> None:
    """Grounding binds N4 to active B, while run subject S remains a separate identity."""

    subject = _problem("stable_subject_s")
    active_basis = subject.model_copy(update={"runtime_hints": {"revision": "B1"}})
    foreign_basis = subject.model_copy(update={"runtime_hints": {"revision": "B2"}})
    subject_ref = gy_content_hash(subject.model_dump(mode="json"))
    active_basis_ref = gy_content_hash(active_basis.model_dump(mode="json"))
    foreign_basis_ref = gy_content_hash(foreign_basis.model_dump(mode="json"))
    assert subject_ref != active_basis_ref
    assert active_basis_ref != foreign_basis_ref

    content_hash = "sha256:" + "4" * 64
    candidate = {
        "candidate_id": "candidate_active_basis",
        "atom": {
            "content_hash": content_hash,
            "problem_frame_ref": active_basis_ref,
            "target_world_slots": ("firm_survival",),
            "world_model_record_ref": "world_model_record_active_basis",
        },
    }
    disposition = {
        "proposal_id": "proposal_active_basis",
        "candidate_id": candidate["candidate_id"],
        "raw_candidate_hash": content_hash,
        "disposition": "shadow_bound",
        "selected_relation": "exact",
        "identified_atom_id": "atom_active_basis",
        "shadow_atom_content_hash": content_hash,
        "certificate_chain": {},
    }
    result = {
        "design_problem_ref": active_basis_ref,
        "grounding_dispositions": (disposition,),
    }

    control = PolicyGroundingPort()(
        candidate=candidate,
        problem=active_basis,
        cycle_index=1,
        generation_result=result,
    )
    assert control.status == "grounded_shadow"
    assert control.current_valid is False  # candidate work only, never current authority

    foreign_result = {**result, "design_problem_ref": foreign_basis_ref}
    candidate_markers = (
        candidate["candidate_id"],
        candidate["atom"]["content_hash"],
        candidate["atom"]["problem_frame_ref"],
        candidate["atom"]["target_world_slots"],
    )
    assert candidate_markers == (
        "candidate_active_basis",
        content_hash,
        active_basis_ref,
        ("firm_survival",),
    )
    assert result["design_problem_ref"] == active_basis_ref
    assert foreign_result["design_problem_ref"] == foreign_basis_ref
    assert foreign_result["grounding_dispositions"] is result["grounding_dispositions"]
    refused = PolicyGroundingPort()(
        candidate=candidate,
        problem=active_basis,
        cycle_index=1,
        generation_result=foreign_result,
    )
    assert refused.status == "grounding_unavailable"
    assert "generation_result_problem_scope_mismatch" in refused.issue_codes
    assert refused.acquisition_requirement is not None
    assert candidate_markers == (
        candidate["candidate_id"],
        candidate["atom"]["content_hash"],
        candidate["atom"]["problem_frame_ref"],
        candidate["atom"]["target_world_slots"],
    )

    foreign_candidate = {
        **candidate,
        "atom": {**candidate["atom"], "problem_frame_ref": foreign_basis_ref},
    }
    assert foreign_candidate["candidate_id"] == candidate["candidate_id"]
    assert foreign_candidate["atom"]["content_hash"] == content_hash
    assert foreign_candidate["atom"]["target_world_slots"] == ("firm_survival",)
    assert result["grounding_dispositions"] is foreign_result["grounding_dispositions"]
    foreign_atom = PolicyGroundingPort()(
        candidate=foreign_candidate,
        problem=active_basis,
        cycle_index=1,
        generation_result=result,
    )
    assert foreign_atom.status == "grounding_unavailable"
    assert "candidate_problem_scope_mismatch" in foreign_atom.issue_codes


@pytest.mark.asyncio
async def test_candidate_owner_target_missing_fails_closed_through_cgf_grounding() -> None:
    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(missing_owner_target=True),
        grounding_port=PolicyGroundingPort(),
        value_port=PendingN8ValuePort(),
    )

    run = await controller.run(_problem(), budget_state=_budget(), max_cycles=1)

    assert run.cycles[0].grounding.status == "grounding_unavailable"
    assert "candidate_owner_target_missing" in run.cycles[0].grounding.issue_codes
    assert run.fronts.decision.candidate_ids == ()


@pytest.mark.asyncio
async def test_proxy_gap_candidate_stays_quarantined_before_any_promotion() -> None:
    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(proxy_gap=True),
        grounding_port=PolicyGroundingPort(),
        value_port=PendingN8ValuePort(),
        promotion_port=_FabricatedPromotionPort(),
        authority_scope="contract_testing",
    )

    run = await controller.run(_problem(), budget_state=_budget(), max_cycles=1)

    summary = run.candidate_summaries[0]
    assert summary.front == "quarantine"
    assert summary.adversarial_validation_status == "completed_shadow_only"
    assert summary.quarantine_action == "adversarial_validate"
    assert run.fronts.decision.candidate_ids == ()
    assert run.fronts.quarantine.candidate_ids == (summary.candidate_id,)


def test_real_cg4_proxy_gap_shape_routes_to_quarantine() -> None:
    result, candidate = _real_cg4_proxy_gap_result()
    problem = _recorded_problem_for_candidate(candidate)

    grounding = PolicyGroundingPort()(
        candidate=candidate,
        problem=problem,
        cycle_index=0,
        generation_result=result,
    )

    assert grounding.quarantine_action == "adversarial_validate"
    summary = CandidateSummary(
        candidate_id=grounding.candidate_id,
        content_hash=candidate["atom"]["content_hash"],
        cycle_index=0,
        generation_channel="n4_owner",
        proxy_score=0.95,
        voi_estimate=0.6,
        grounding_status=grounding.status,
        grounding_source=grounding.grounding_source,
        grounding_disposition=grounding.grounding_disposition,
        grounding_score=grounding.grounding_score,
        current_valid=grounding.current_valid,
        front="quarantine",
        high_proxy=True,
        low_grounding=True,
        quarantine_action=grounding.quarantine_action,
        adversarial_validation_status="completed_shadow_only",
    )
    fronts = _derive_fronts((summary,))

    assert fronts.decision.candidate_ids == ()
    assert fronts.quarantine.candidate_ids == (summary.candidate_id,)


def test_raw_dict_promotion_receipt_cannot_enter_decision_front() -> None:
    current_valid = CandidateSummary(
        candidate_id="candidate_current_valid",
        content_hash="sha256:" + "2" * 64,
        cycle_index=0,
        generation_channel="n4_owner",
        proxy_score=0.2,
        voi_estimate=0.1,
        grounding_status="current_valid",
        grounding_source="cgf_firewall",
        grounding_disposition="shadow_bound",
        grounding_score=0.9,
        current_valid=True,
        front="research",
        high_proxy=False,
        low_grounding=False,
    )
    conflict = current_valid.model_copy(
        update={
            "candidate_id": "candidate_conflict",
            "content_hash": "sha256:" + "3" * 64,
            "proxy_score": 0.95,
            "grounding_score": 0.2,
            "front": "quarantine",
            "high_proxy": True,
            "low_grounding": True,
            "quarantine_action": "adversarial_validate",
            "adversarial_validation_status": "required_before_decision",
        }
    )
    promoted = _apply_promotion_to_summaries(
        (current_valid, conflict),
        PromotionPortObservation(
            status="certified_current_valid",
            certified_candidate_ids=("candidate_current_valid", "candidate_conflict"),
            receipts=(
                _n9_receipt("candidate_current_valid", consumer_promotable=True),
                _n9_receipt("candidate_conflict", consumer_promotable=True),
            ),
        ),
    )
    fronts = _derive_fronts(tuple(promoted))

    assert fronts.decision.candidate_ids == ()
    assert fronts.research.candidate_ids == ("candidate_current_valid",)
    assert fronts.quarantine.candidate_ids == ("candidate_conflict",)


def test_blocked_value_candidate_cannot_be_promoted_to_decision_front() -> None:
    current_valid = CandidateSummary(
        candidate_id="candidate_value_blocked",
        content_hash="sha256:" + "2" * 64,
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
        (current_valid,),
        PromotionPortObservation(
            status="certified_current_valid",
            certified_candidate_ids=("candidate_value_blocked",),
            receipts=(_n9_receipt("candidate_value_blocked", consumer_promotable=True),),
        ),
    )
    fronts = _derive_fronts(tuple(promoted))

    assert fronts.decision.candidate_ids == ()
    assert fronts.research.candidate_ids == ("candidate_value_blocked",)


def test_nonbinding_resolution_cannot_become_promotion_eligible() -> None:
    """World identity for refusal cannot be laundered into decision authority."""

    nonbinding = CandidateSummary(
        candidate_id="candidate_nonbinding_world_identity",
        content_hash="sha256:" + "6" * 64,
        cycle_index=0,
        generation_channel="n4_owner",
        proxy_score=0.9,
        voi_estimate=0.8,
        grounding_status="grounding_gap",
        grounding_source="cgf_firewall",
        grounding_disposition="non_binding_abstain",
        grounding_score=0.2,
        current_valid=False,
        value_status="value_blocked",
        value_decision_grade="blocked",
        value_blockers=("method_estimand_binding_mismatch",),
        front="research",
        high_proxy=True,
        low_grounding=True,
    )
    projected = _apply_promotion_to_summaries(
        (nonbinding,),
        PromotionPortObservation(
            status="certified_current_valid",
            certified_candidate_ids=(nonbinding.candidate_id,),
            receipts=(_n9_receipt(nonbinding.candidate_id, consumer_promotable=True),),
        ),
    )
    fronts = _derive_fronts(tuple(projected))

    assert fronts.decision.candidate_ids == ()
    assert projected[0].certified_by_n9 is False


def test_contract_lane_n9_receipt_cannot_enter_decision_front() -> None:
    current_valid = CandidateSummary(
        candidate_id="candidate_contract_lane",
        content_hash="sha256:" + "2" * 64,
        cycle_index=0,
        generation_channel="n4_owner",
        proxy_score=0.2,
        voi_estimate=0.1,
        grounding_status="current_valid",
        grounding_source="cgf_firewall",
        grounding_disposition="shadow_bound",
        grounding_score=0.9,
        current_valid=True,
        front="research",
        high_proxy=False,
        low_grounding=False,
    )
    promoted = _apply_promotion_to_summaries(
        (current_valid,),
        PromotionPortObservation(
            status="certified_current_valid",
            certified_candidate_ids=("candidate_contract_lane",),
            receipts=(
                _n9_receipt(
                    "candidate_contract_lane",
                    consumer_promotable=False,
                    promotion_lane="contract_testing",
                    non_promotable_reason="non_production_anchor_scope",
                ),
            ),
        ),
    )
    fronts = _derive_fronts(tuple(promoted))

    assert fronts.decision.candidate_ids == ()
    assert fronts.research.candidate_ids == ("candidate_contract_lane",)


class _BlockedValuePort:
    def __call__(self, **kwargs: Any) -> ValuePortObservation:
        del kwargs
        return ValuePortObservation(
            status="value_blocked",
            authority_blockers=("uncalibrated_forecast_minted_value",),
            reason="S10 calibration refused authority.",
            decision_grade="blocked",
        )


class _DataGapValuePort:
    def __call__(self, **kwargs: Any) -> ValuePortObservation:
        candidate = kwargs["candidate"]
        problem = kwargs["problem"]
        return ValuePortObservation(
            status="value_blocked",
            candidate_id=candidate.candidate_id,
            authority_blockers=("acquire_data:value_panel_data_missing",),
            reason="Owner-bound panel observations are missing.",
            decision_grade="blocked",
            acquisition_requirement=l1_variable_availability_requirement_gap(
                candidate_id=candidate.candidate_id,
                candidate_content_hash=candidate.atom.content_hash,
                design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
                availability=L1VariableAvailability(
                    variable_id="firm_survival",
                    status="unavailable",
                    dataset_count=0,
                    metric_binding_count=0,
                    observation_count=0,
                    coverage_ref=(
                        "repo://production_data/dataset_catalog.duckdb#variable/firm_survival"
                    ),
                ),
                authority_level=problem.authority_profile.requested_authority_level,
            ),
        )


class _CostedDataGapValuePort:
    def __call__(self, **kwargs: Any) -> ValuePortObservation:
        candidate = kwargs["candidate"]
        problem = kwargs["problem"]
        variable_id = "administrative_tax_receipts"
        return ValuePortObservation(
            status="value_blocked",
            candidate_id=candidate.candidate_id,
            authority_blockers=("acquire_data:value_panel_data_missing",),
            reason="Current owner tax-receipt observations are missing.",
            decision_grade="blocked",
            acquisition_requirement=l1_variable_availability_requirement_gap(
                candidate_id=candidate.candidate_id,
                candidate_content_hash=candidate.atom.content_hash,
                design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
                availability=L1VariableAvailability(
                    variable_id=variable_id,
                    status="unavailable",
                    dataset_count=0,
                    metric_binding_count=0,
                    observation_count=0,
                    coverage_ref=(
                        f"repo://production_data/dataset_catalog.duckdb#variable/{variable_id}"
                    ),
                ),
                authority_level=problem.authority_profile.requested_authority_level,
            ),
        )


class _OverlayDataGapValuePort:
    def __call__(self, **kwargs: Any) -> ValuePortObservation:
        candidate = kwargs["candidate"]
        problem = kwargs["problem"]
        variable_id = "cells.distress_score"
        return ValuePortObservation(
            status="value_blocked",
            candidate_id=candidate.candidate_id,
            authority_blockers=("acquire_data:value_panel_data_missing",),
            reason="Current owner distress observations are missing.",
            decision_grade="blocked",
            acquisition_requirement=l1_variable_availability_requirement_gap(
                candidate_id=candidate.candidate_id,
                candidate_content_hash=candidate.atom.content_hash,
                design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
                availability=L1VariableAvailability(
                    variable_id=variable_id,
                    status="unavailable",
                    dataset_count=0,
                    metric_binding_count=0,
                    observation_count=0,
                    coverage_ref=(
                        f"repo://production_data/dataset_catalog.duckdb#variable/{variable_id}"
                    ),
                ),
                authority_level=problem.authority_profile.requested_authority_level,
            ),
        )


@_requires_owner_catalog
def test_phase5_value_port_configuration_preserves_manifest_omission() -> None:
    """Constructor serialization preserves omission and explicit invalid source."""
    problem, context, candidate = _canonical_strict_world_case()
    simulation = SimulationPortObservation(
        candidate_id=candidate.candidate_id,
        status="joint_simulated",
        simulation_ref="sha256:" + "9" * 64,
        world_model_record=context.world_model_record,
        k_world_ref_before=context.world_model_record.content_hash,
        k_world_ref_after=context.world_model_record.content_hash,
    )
    execution_context = generation_cycle_module.simulation_value_execution_context(
        candidate=candidate, simulation=simulation, problem=problem,
    )
    omitted = generation_cycle_module.FoundryValuePort(evaluation_context=execution_context)
    omitted_inputs = omitted._selection_inputs()
    assert "observation_to_contract_manifest" not in omitted_inputs
    assert generation_cycle_module._select_value_method(
        candidate={}, problem={}, inputs=omitted_inputs,
    )["status"] == "selected"
    supplied_null = generation_cycle_module.FoundryValuePort(
        evaluation_context=execution_context, observation_to_contract_manifest=None,
    )
    null_inputs = supplied_null._selection_inputs()
    assert "observation_to_contract_manifest" in null_inputs
    assert generation_cycle_module._select_value_method(
        candidate={}, problem={}, inputs=null_inputs,
    )["status"] == "blocked"
    with pytest.raises(ValueError, match="value_method_manifest_source_invalid"):
        generation_cycle_module._value_method_route_constraint(
            candidate={}, problem={}, inputs=null_inputs,
        )


@_requires_owner_catalog
def test_default_value_port_binds_the_actual_n5_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lazy N8 wrapper binds and exercises the N5 observation from this call."""

    problem, context, candidate = _canonical_strict_world_case()
    world = context.world_model_record
    simulation = SimulationPortObservation(
        candidate_id=candidate.candidate_id,
        status="joint_simulated",
        simulation_ref="sha256:" + "9" * 64,
        world_model_record=world,
        k_world_ref_before=world.content_hash,
        k_world_ref_after=world.content_hash,
    )
    owner_calls: list[tuple[object, ...]] = []

    class ProbeOwnerGateway:
        def load_value_data_profile(self, **kwargs: Any) -> Any:
            owner_calls.append(
                (kwargs["candidate"], kwargs["problem"], kwargs["world_record"])
            )
            raise generation_cycle_module.ValueOwnerAccessError("fresh_n5_owner_probe")

        def produce_forecast_inputs(self, **kwargs: Any) -> Any:
            del kwargs
            raise AssertionError("forecast_called_after_owner_probe")

        def build_transport_inputs(self, **kwargs: Any) -> Any:
            del kwargs
            raise AssertionError("transport_called_after_owner_probe")

    owner_gateway = ProbeOwnerGateway()
    captured_init: list[dict[str, Any]] = []
    real_foundry_port = generation_cycle_module.FoundryValuePort

    class CapturingFoundryValuePort:
        def __init__(self, **kwargs: Any) -> None:
            captured_init.append(kwargs)
            self._delegate = real_foundry_port(**kwargs)
            assert "observation_to_contract_manifest" not in self._delegate._selection_inputs()

        def __call__(self, **kwargs: Any) -> ValuePortObservation:
            return self._delegate(**kwargs)

    monkeypatch.setattr(
        generation_cycle_module,
        "FoundryValuePort",
        CapturingFoundryValuePort,
    )
    wrapper = generation_cycle_module._DefaultSimulationBoundFoundryValuePort(
        repo_root=REPO_ROOT,
        cycle_substrate_context=context,
        owner_gateway=owner_gateway,
    )

    observation = wrapper(
        candidate=candidate,
        simulation=simulation,
        problem=problem,
        cycle_index=7,
    )

    assert observation.status == "value_blocked"
    assert observation.authority_blockers == ("fresh_n5_owner_probe",)
    assert owner_calls == [(candidate, problem, world)]
    assert len(captured_init) == 1
    captured = captured_init[0]
    execution_context = captured["evaluation_context"]
    assert captured["owner_gateway"] is owner_gateway
    assert execution_context.evaluation_mode == "simulate_only"
    assert execution_context.design_problem_ref == gy_content_hash(problem.model_dump(mode="json"))
    assert execution_context.candidate_ref.artifact_id == candidate.candidate_id
    assert execution_context.candidate_ref.content_hash == candidate.atom.content_hash
    assert execution_context.world_model_record_ref.artifact_id == world.world_model_record_id
    assert execution_context.world_model_record_ref.content_hash == world.content_hash
    assert execution_context.evaluation_input_refs[0].content_hash == simulation.simulation_ref


class _WorldKnowledgeGapValuePort:
    def __call__(self, **kwargs: Any) -> ValuePortObservation:
        del kwargs
        return ValuePortObservation(
            status="value_blocked",
            candidate_id="candidate_cgf_shadow",
            authority_blockers=("treatment_assignment_not_owner_derived",),
            reason="Owner treatment assignment is missing.",
            decision_grade="blocked",
            acquisition_requirement=value_input_world_knowledge_requirement_gap(
                claim_ref="value-claim:candidate_cgf_shadow"
            ),
        )


class _TransplantedWorldKnowledgeGapValuePort:
    def __call__(self, **kwargs: Any) -> ValuePortObservation:
        del kwargs
        return ValuePortObservation(
            status="value_blocked",
            candidate_id="candidate_from_another_cycle",
            authority_blockers=("treatment_assignment_not_owner_derived",),
            reason="Transplanted owner-treatment gap.",
            decision_grade="blocked",
            acquisition_requirement=value_input_world_knowledge_requirement_gap(
                claim_ref="value-claim:candidate_from_another_cycle"
            ),
        )


class _RepointedDataGapValuePort:
    def __call__(self, **kwargs: Any) -> ValuePortObservation:
        candidate = kwargs["candidate"]
        problem = kwargs["problem"]
        return ValuePortObservation(
            status="value_blocked",
            candidate_id=candidate.candidate_id,
            authority_blockers=("acquire_data:value_panel_data_missing",),
            reason="Owner data gap repointed to another candidate payload.",
            decision_grade="blocked",
            acquisition_requirement=l1_variable_availability_requirement_gap(
                candidate_id=candidate.candidate_id,
                candidate_content_hash="sha256:" + "0" * 64,
                design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
                availability=L1VariableAvailability(
                    variable_id="firm_survival",
                    status="unavailable",
                    dataset_count=0,
                    metric_binding_count=0,
                    observation_count=0,
                    coverage_ref=(
                        "repo://production_data/dataset_catalog.duckdb#variable/firm_survival"
                    ),
                ),
                authority_level=problem.authority_profile.requested_authority_level,
            ),
        )


@pytest.mark.asyncio
async def test_value_block_feeds_revision_before_promotion() -> None:
    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        value_port=_BlockedValuePort(),
        promotion_port=_FabricatedPromotionPort(),
        authority_scope="contract_testing",
    )

    run = await controller.run(_problem(), budget_state=_budget(), max_cycles=1)

    assert run.value_port.status == "value_blocked"
    assert run.cycles[0].counterexample.counterexample_class == "value_gap"
    assert run.cycles[0].counterexample.diagnostic.code.endswith(
        "uncalibrated_forecast_minted_value"
    )
    assert run.fronts.decision.candidate_ids == ()


@pytest.mark.asyncio
async def test_value_data_gap_routes_to_n7_acquisition_terminal() -> None:
    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        value_port=_DataGapValuePort(),
    )

    run = await controller.run(_problem(), budget_state=_budget(), max_cycles=1)

    assert run.value_port.status == "value_blocked"
    assert run.cycles[0].terminal_kind == "acquisition_required"
    assert run.cycles[0].revision_request.revision_strategy == "acquire_or_elicit"
    assert run.cycles[0].refinement_decision.decision == "acquire"
    assert run.cycles[0].search_iteration.status == "acquisition_required"
    assert (
        run.cycles[0].revision_request.strategy_payload["acquisition_request"]["driver"]
        == "acquire_data:value_panel_data_missing"
    )
    assert run.cycles[0].acquisition_routing_report is not None
    assert run.cycles[0].acquisition_receipt is None
    record = run.cycles[0].acquisition_routing_report.acquisition_records[0]
    assert record.recommended_strategy.value == "production_snapshot_build"
    assert record.terminal_disposition.value == "acquire"
    assert record.claim_ref == "value-claim:candidate_cgf_shadow"
    assert run.fronts.decision.candidate_ids == ()


@pytest.mark.asyncio
async def test_canonical_n7_route_attaches_exact_owner_cost_basis() -> None:
    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(target_world_slots=("administrative_tax_receipts",)),
        value_port=_CostedDataGapValuePort(),
    )

    run = await controller.run(_problem(), budget_state=_budget(), max_cycles=1)

    cycle = run.cycles[0]
    assert cycle.acquisition_routing_report is not None
    assert cycle.acquisition_cost_basis_record is not None
    cost = cycle.acquisition_cost_basis_record
    assert cost.missing_distribution == "administrative_tax_receipts"
    assert (
        cost.strategy
        == cycle.acquisition_routing_report.acquisition_records[0].recommended_strategy
    )
    assert cost.schedule_content_hash == (
        "sha256:258c2dd22214b8a3bf9157cb6ad186b6320317b526d2f951098bd72ead9328d3"
    )
    assert cycle.acquisition_cost_basis_hash == cost.record_content_hash


@pytest.mark.asyncio
@_requires_owner_catalog
async def test_active_overlay_reentry_is_exact_direct_and_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.unit.runtime.quality.test_acquisition_executor import (
        _activate_real_epoch_scenario,
        _real_epoch_scenario,
    )

    problem = _problem("ds15_active_overlay_reentry")
    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(target_world_slots=("cells.distress_score",)),
        value_port=_OverlayDataGapValuePort(),
    )
    source_run = await controller.run(problem, budget_state=_budget(), max_cycles=1)
    source_cycle = source_run.cycles[0]
    scenario = _real_epoch_scenario(tmp_path / "epoch")
    _production, activated = _activate_real_epoch_scenario(scenario)
    calls: list[tuple[object, ...]] = []

    async def direct_cycle(
        received_problem: DesignProblem,
        *,
        cycle_index: int,
        budget_state: BudgetState,
        previous_cycle: object,
        value_port_override: object,
        stable_design_problem_ref: str,
    ) -> tuple[object, tuple[CandidateSummary, ...]]:
        assert received_problem is problem
        assert stable_design_problem_ref == source_run.design_problem_ref
        assert cycle_index == source_cycle.cycle_index + 1
        assert previous_cycle is source_cycle
        assert isinstance(
            value_port_override,
            generation_cycle_module._DefaultSimulationBoundFoundryValuePort,
        )
        assert isinstance(value_port_override.owner_gateway, RealValueOwnerGateway)
        assert value_port_override.owner_gateway.catalog_overlay_path == (
            scenario.overlay.overlay_path
        )
        calls.append((received_problem, previous_cycle, value_port_override))
        return (
            source_cycle.model_copy(update={"cycle_index": cycle_index}),
            tuple(
                row.model_copy(update={"cycle_index": cycle_index})
                for row in source_run.candidate_summaries
            ),
        )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise AssertionError("legacy_or_world_write_reentry_path_called")

    monkeypatch.setattr(controller, "_run_cycle", direct_cycle)
    monkeypatch.setattr(controller, "run", forbidden)
    monkeypatch.setattr(controller, "_reenter_cycle_after_n7_acquisition", forbidden)
    monkeypatch.setattr(controller, "_run_n7_acquisition_if_requested", forbidden)
    monkeypatch.setattr(generation_cycle_module, "run_acquisition_closed_loop", forbidden)

    receipt = await controller.reenter_after_active_acquisition_overlay(
        original_run=source_run,
        source_cycle=source_cycle,
        problem=problem,
        overlay_receipt=activated,
        baseline_path=scenario.authority.baseline_path,
        overlay_path=scenario.overlay.overlay_path,
        budget_state=_budget(),
    )

    assert isinstance(receipt, AcquisitionOverlayReentryReceipt)
    assert len(calls) == 1
    assert receipt.source_run_id == source_run.run_id
    assert receipt.source_candidate_ref == source_cycle.selected_candidate_ref
    assert receipt.overlay_receipt_ref == str(activated.receipt_ref.artifact_id)
    assert receipt.overlay_receipt_content_hash == activated.receipt_content_hash
    assert receipt.epoch_id == activated.epoch_id
    assert receipt.passport_id == activated.passport_id
    assert receipt.overlay_path == scenario.overlay.overlay_path.as_posix()
    assert receipt.new_cycle.cycle_index == source_cycle.cycle_index + 1
    assert source_run.cycles == (source_cycle,)

    context_problem, context, context_candidate = _canonical_strict_world_case()
    context_world = context.world_model_record
    context_simulation = SimulationPortObservation(
        candidate_id=context_candidate.candidate_id,
        status="joint_simulated",
        simulation_ref="sha256:" + "8" * 64,
        world_model_record=context_world,
        k_world_ref_before=context_world.content_hash,
        k_world_ref_after=context_world.content_hash,
    )
    stale_context = generation_cycle_module.simulation_value_execution_context(
        candidate=context_candidate,
        simulation=context_simulation,
        problem=context_problem,
    ).model_copy(update={"evaluation_mode": "deployment"})

    class ForbiddenOwnerGateway:
        def __getattr__(self, name: str) -> Any:
            raise AssertionError(f"stale_context_reached_owner:{name}")

    stale_controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(target_world_slots=("cells.distress_score",)),
        value_port=generation_cycle_module.FoundryValuePort(
            evaluation_context=stale_context,
            owner_gateway=ForbiddenOwnerGateway(),
        ),
    )
    monkeypatch.setattr(stale_controller, "_run_cycle", forbidden)
    with pytest.raises(
        GenerationCycleError,
        match="acquisition_reentry_evaluation_context_rebinding_required",
    ):
        await stale_controller.reenter_after_active_acquisition_overlay(
            original_run=source_run,
            source_cycle=source_cycle,
            problem=problem,
            overlay_receipt=activated,
            baseline_path=scenario.authority.baseline_path,
            overlay_path=scenario.overlay.overlay_path,
            budget_state=_budget(),
        )


@pytest.mark.asyncio
async def test_active_overlay_reentry_rejects_binding_and_trace_mutations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import duckdb

    from tests.unit.runtime.quality.test_acquisition_executor import (
        _activate_real_epoch_scenario,
        _real_epoch_scenario,
    )

    problem = _problem("ds15_overlay_reentry_mutations")
    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(target_world_slots=("cells.distress_score",)),
        value_port=_OverlayDataGapValuePort(),
    )
    source_run = await controller.run(problem, budget_state=_budget(), max_cycles=1)
    source_cycle = source_run.cycles[0]
    scenario = _real_epoch_scenario(tmp_path / "epoch-a")
    _production, activated = _activate_real_epoch_scenario(scenario)

    async def forbidden_cycle(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise AssertionError("reentry_cycle_called_for_mismatched_owner_state")

    monkeypatch.setattr(controller, "_run_cycle", forbidden_cycle)
    arguments = {
        "original_run": source_run,
        "source_cycle": source_cycle,
        "problem": problem,
        "overlay_receipt": activated,
        "baseline_path": scenario.authority.baseline_path,
        "overlay_path": scenario.overlay.overlay_path,
        "budget_state": _budget(),
    }

    with pytest.raises(
        GenerationCycleError,
        match="acquisition_reentry_case_binding_mismatch",
    ):
        await controller.reenter_after_active_acquisition_overlay(
            **{**arguments, "problem": _problem("another_case")}
        )

    mismatched_run = await GenerationCycleController(
        generation_port=_CgfGenerationPort(target_world_slots=("administrative_tax_receipts",)),
        value_port=_CostedDataGapValuePort(),
    ).run(problem, budget_state=_budget(), max_cycles=1)
    with pytest.raises(
        GenerationCycleError,
        match="acquisition_reentry_requirement_overlay_mismatch",
    ):
        await controller.reenter_after_active_acquisition_overlay(
            **{
                **arguments,
                "original_run": mismatched_run,
                "source_cycle": mismatched_run.cycles[0],
            }
        )

    with pytest.raises(
        GenerationCycleError,
        match="acquisition_reentry_activation_receipt_mismatch",
    ):
        await controller.reenter_after_active_acquisition_overlay(
            **{
                **arguments,
                "overlay_receipt": activated.model_copy(
                    update={"epoch_id": activated.epoch_id + 1}
                ),
            }
        )

    with pytest.raises(
        GenerationCycleError,
        match="acquisition_reentry_overlay_binding_mismatch",
    ):
        await controller.reenter_after_active_acquisition_overlay(
            **{**arguments, "overlay_path": tmp_path / "overlay-b.duckdb"}
        )

    connection = duckdb.connect(str(scenario.overlay.overlay_path))
    try:
        connection.execute(
            "DELETE FROM acquisition_semantic_receipts "
            "WHERE receipt_kind = 'epoch.activated_overlay_admission_receipt'"
        )
    finally:
        connection.close()
    with pytest.raises(
        GenerationCycleError,
        match="acquisition_reentry_post_epoch_trace_missing",
    ):
        await controller.reenter_after_active_acquisition_overlay(**arguments)


@pytest.mark.asyncio
async def test_honest_single_cycle_acquisition_terminal_validates() -> None:
    """A coherent one-cycle terminal is not a missing positive denominator."""

    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        value_port=_DataGapValuePort(),
        repo_root=REPO_ROOT,
    )

    run = await controller.run(_problem(), budget_state=_budget(), max_cycles=1)

    assert len(run.cycles) == 1
    assert run.cycles[0].terminal_kind == "acquisition_required"
    assert validate_generation_cycle_candidate_run(run) == ()
    strict_issue_codes = {
        issue["code"] for issue in validate_generation_cycle_run(run, repo_root=REPO_ROOT)
    }
    assert "strangle_receipt_currentness_not_established" in strict_issue_codes
    assert "single_pass_fixture_survives_as_production_cycle" not in strict_issue_codes


@pytest.mark.asyncio
async def test_fabricated_single_cycle_unreachable_terminal_combination_is_red() -> None:
    """A supported terminal label cannot override the real stage state."""

    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        value_port=_DataGapValuePort(),
    )
    run = await controller.run(_problem(), budget_state=_budget(), max_cycles=1)
    fabricated_cycle = run.cycles[0].model_copy(update={"terminal_kind": "frontier_stable"})
    fabricated_run = run.model_copy(update={"cycles": (fabricated_cycle,)})

    issue_codes = {
        str(issue.get("code")) for issue in validate_generation_cycle_run(fabricated_run)
    }

    assert "incoherent_single_terminal_state" in issue_codes


@pytest.mark.asyncio
async def test_empty_completed_cycle_run_is_red() -> None:
    """The one-directional relaxation still requires a non-empty denominator."""

    run = await GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        value_port=_DataGapValuePort(),
    ).run(_problem(), budget_state=_budget(), max_cycles=1)

    empty = run.model_copy(update={"cycles": ()})
    issue_codes = {str(issue.get("code")) for issue in validate_generation_cycle_run(empty)}

    assert "cycle_denominator_empty" in issue_codes


def test_every_promotion_input_is_preceded_by_produce_persist_and_fresh_resolve(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    events: list[str] = []
    original_gate = runtime.open_world_authority.prepare_verified_projection
    original_n9 = promotion_sequence_module._run_canonical_promotion_sequence_with_owner_gate

    def prepare_gate(**kwargs: Any) -> Any:
        events.append("fresh_resolve_vector")
        return original_gate(**kwargs)

    def run_n9(*args: Any, **kwargs: Any) -> Any:
        events.append("n9")
        return original_n9(*args, **kwargs)

    monkeypatch.setattr(
        runtime.open_world_authority,
        "prepare_verified_projection",
        prepare_gate,
    )
    monkeypatch.setattr(
        promotion_sequence_module,
        "_run_canonical_promotion_sequence_with_owner_gate",
        run_n9,
    )
    monkeypatch.setattr(
        promotion_sequence_module,
        "_legacy_policy_promotion_callers",
        lambda repo_root: (),
    )
    summary = _open_world_summary()
    problem = _problem(f"open_world_ordered_gate_{uuid4().hex}")
    admitted_batch = _positive_epoch_admitted_batch(
        runtime=runtime,
        problem=problem,
        summaries=(summary,),
    )
    events.clear()
    observation = CanonicalN9PromotionPort(
        promotion_runtime=runtime,
        epoch_n9_evidence_resolver=runtime.epoch_n9_evidence_resolver,
        repo_root=REPO_ROOT,
    )(
        admitted_batch=admitted_batch,
        problem=problem,
        deployment_identity=_canonical_loaded_deployment_identity(),
    )

    assert events == ["fresh_resolve_vector", "n9"]
    assert observation.status == "not_promoted"
    receipt = CanonicalPromotionReceipt.model_validate(observation.receipts[0])
    gate = receipt.owner_projection.open_world_gate
    assert gate is not None
    assert gate.status == "not_established"
    assert "open_world_risk:deployment_scope_not_established" in receipt.refusal_reasons


def _run_open_world_n9_case(
    *, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[PromotionRuntime, DesignProblem, CandidateSummary, CanonicalPromotionReceipt]:
    monkeypatch.setattr(
        promotion_sequence_module,
        "_legacy_policy_promotion_callers",
        lambda repo_root: (),
    )
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    problem = _problem(f"open_world_replay_{tmp_path.name}_{uuid4().hex}")
    summary = _open_world_summary()
    admitted_batch = _positive_epoch_admitted_batch(
        runtime=runtime,
        problem=problem,
        summaries=(summary,),
    )
    observation = CanonicalN9PromotionPort(
        promotion_runtime=runtime,
        epoch_n9_evidence_resolver=runtime.epoch_n9_evidence_resolver,
        repo_root=REPO_ROOT,
    )(
        admitted_batch=admitted_batch,
        problem=problem,
        deployment_identity=_canonical_loaded_deployment_identity(),
    )
    assert observation.receipts
    return (
        runtime,
        problem,
        summary,
        CanonicalPromotionReceipt.model_validate(observation.receipts[0]),
    )


def test_offline_replay_recomputes_open_world_vector_and_verifier_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, problem, summary, receipt = _run_open_world_n9_case(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )
    fresh_store = FileSystemCAS(tmp_path / "cas")
    fresh_resolver = OpenWorldRiskVectorArtifactRepository(store=fresh_store)
    fresh_epoch_resolver = PromotionRuntime(
        store=fresh_store,
        completed_epoch_batches=DecisionValidityService(fresh_store),
    ).epoch_n9_evidence_resolver

    issues = validate_canonical_promotion_receipt(
        receipt,
        candidate_summary=summary,
        design_problem=problem,
        open_world_resolver=fresh_resolver,
        epoch_validity_resolver=fresh_epoch_resolver,
    )

    assert issues == ()
    assert runtime.resolver is not fresh_resolver


def test_offline_replay_rejects_missing_or_mutated_epoch_gate_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, problem, summary, receipt = _run_open_world_n9_case(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )

    missing = validate_canonical_promotion_receipt(
        receipt,
        candidate_summary=summary,
        design_problem=problem,
        open_world_resolver=runtime.resolver,
    )
    assert "epoch_validity_resolver_not_established" in {issue["code"] for issue in missing}

    projection = receipt.owner_projection.epoch_validity_projection
    assert projection is not None
    gate_blob, _ = runtime.store._paths(projection.gate_receipt_ref.artifact_id)
    gate_blob.write_bytes(b'{"forged":"gate"}')

    rejected = validate_canonical_promotion_receipt(
        receipt,
        candidate_summary=summary,
        design_problem=problem,
        open_world_resolver=runtime.resolver,
        epoch_validity_resolver=runtime.epoch_n9_evidence_resolver,
    )

    assert "epoch_validity_gate_evidence_unresolved" in {issue["code"] for issue in rejected}


@pytest.mark.asyncio
async def test_generation_run_carries_epoch_owner_into_decision_front_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Losing the owned resolver at the run boundary must fail even on a refusal."""

    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    original_apply = generation_cycle_module._apply_promotion_to_summaries
    received_resolvers: list[object] = []

    def apply_with_replay(*args: Any, **kwargs: Any) -> list[CandidateSummary]:
        received_resolvers.append(kwargs.get("epoch_validity_resolver"))
        return original_apply(*args, **kwargs)

    monkeypatch.setattr(
        generation_cycle_module,
        "_apply_promotion_to_summaries",
        apply_with_replay,
    )
    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        value_port=_DataGapValuePort(),
        promotion_runtime=runtime,
        repo_root=REPO_ROOT,
    )
    run = await controller.run(
        _problem("epoch_owner_decision_front_bridge"),
        budget_state=_budget(),
        max_cycles=1,
    )

    assert received_resolvers == [runtime.epoch_n9_evidence_resolver], (
        "epoch_owner_forwarding_missing_at_generation_run"
    )
    stored = runtime.store.put_json(
        run.model_dump(mode="json"),
        ArtifactWriteOptions(kind="test.generation_cycle_run", media_type="application/json"),
        canon.CanonSpec(forbid_floats=False),
    )
    replayed = GenerationCycleRun.model_validate(
        canon.from_canonical_bytes(runtime.store.get_bytes(stored.artifact_id))
    )
    assert replayed.fronts.decision.candidate_ids == ()
    assert replayed.promotion_port.status == "not_promoted"
    assert replayed.cycles
    assert replayed.candidate_summaries
    assert replayed.promotion_port.reason == (
        "generation_cycle_n6_census_not_established:n6_census_issuer_not_appointed"
    )


@pytest.mark.parametrize("epoch_evidence", ["valid", "missing_resolver", "corrupted_artifact"])
def test_decision_front_replays_epoch_owner_and_preserves_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    epoch_evidence: str,
) -> None:
    """Certification markers cannot replace fresh epoch evidence or erase refusals."""

    runtime, problem, summary, receipt = _run_open_world_n9_case(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )
    stored = runtime.store.put_json(
        receipt.model_dump(mode="json"),
        ArtifactWriteOptions(kind="test.n9_promotion_receipt", media_type="application/json"),
        canon.CanonSpec(forbid_floats=False),
    )
    payload = canon.from_canonical_bytes(runtime.store.get_bytes(stored.artifact_id))
    promotion = PromotionPortObservation(
        status="certified_current_valid",
        certified_candidate_ids=(summary.candidate_id,),
        receipts=(payload,),
    )
    if epoch_evidence == "corrupted_artifact":
        projection = receipt.owner_projection.epoch_validity_projection
        assert projection is not None
        gate_blob, _ = runtime.store._paths(projection.gate_receipt_ref.artifact_id)
        gate_blob.write_bytes(b'{"epoch_gate_marker":"retained_without_owner_evidence"}')
    original_validate = promotion_sequence_module.validate_canonical_promotion_receipt
    replay_issues: list[tuple[dict[str, Any], ...]] = []

    def validate_with_owner(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], ...]:
        issues = original_validate(*args, **kwargs)
        replay_issues.append(issues)
        return issues

    monkeypatch.setattr(
        promotion_sequence_module,
        "validate_canonical_promotion_receipt",
        validate_with_owner,
    )
    result = _apply_promotion_to_summaries(
        (summary,),
        promotion,
        problem=problem,
        open_world_resolver=runtime.resolver,
        epoch_validity_resolver=(
            None if epoch_evidence == "missing_resolver" else runtime.epoch_n9_evidence_resolver
        ),
    )

    assert len(replay_issues) == 1
    codes = {issue["code"] for issue in replay_issues[0]}
    if epoch_evidence == "valid":
        assert replay_issues[0] == (), "epoch_owner_replay_is_not_clean"
    elif epoch_evidence == "missing_resolver":
        assert "epoch_validity_resolver_not_established" in codes
    else:
        assert "epoch_validity_gate_evidence_unresolved" in codes
    assert result == [summary]
    assert _derive_fronts(tuple(result)).decision.candidate_ids == ()
    assert payload["promoted"] is False
    assert payload["refusal_reasons"] == list(receipt.refusal_reasons)


def test_fresh_process_replay_rejects_deleted_or_mutated_open_world_vector(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, problem, summary, receipt = _run_open_world_n9_case(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )
    missing_resolver = OpenWorldRiskVectorArtifactRepository(
        store=FileSystemCAS(tmp_path / "empty-cas")
    )

    issues = validate_canonical_promotion_receipt(
        receipt,
        candidate_summary=summary,
        design_problem=problem,
        open_world_resolver=missing_resolver,
    )

    assert "open_world_vector_unresolved" in {row["code"] for row in issues}

    gate = receipt.owner_projection.open_world_gate
    assert gate is not None
    blob_file, _ = runtime.store._paths(gate.vector_artifact_ref.artifact_id)
    blob_file.write_bytes(b"corrupted-open-world-vector")
    corrupted_issues = validate_canonical_promotion_receipt(
        receipt,
        candidate_summary=summary,
        design_problem=problem,
        open_world_resolver=OpenWorldRiskVectorArtifactRepository(
            store=FileSystemCAS(tmp_path / "cas")
        ),
    )
    assert {row["code"] for row in corrupted_issues} & {
        "open_world_vector_unresolved",
        "open_world_vector_content_mismatch",
    }


def test_remove_vector_keep_gate_markers_fails_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, problem, summary, receipt = _run_open_world_n9_case(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )
    gate = receipt.owner_projection.open_world_gate
    assert gate is not None

    issues = validate_canonical_promotion_receipt(
        receipt,
        candidate_summary=summary,
        design_problem=problem,
        open_world_resolver=OpenWorldRiskVectorArtifactRepository(
            store=FileSystemCAS(tmp_path / "markers-only-cas")
        ),
    )

    assert receipt.owner_projection.open_world_gate == gate
    assert "open_world_vector_unresolved" in {row["code"] for row in issues}


@pytest.mark.asyncio
async def test_value_gap_for_another_candidate_cannot_be_routed() -> None:
    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        value_port=_TransplantedWorldKnowledgeGapValuePort(),
    )

    with pytest.raises(ValueError, match="cycle_stage_candidate_mismatch"):
        await controller.run(_problem(), budget_state=_budget(), max_cycles=1)


@pytest.mark.asyncio
async def test_value_data_gap_cannot_repoint_same_candidate_content() -> None:
    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        value_port=_RepointedDataGapValuePort(),
    )

    with pytest.raises(
        ValueError,
        match="cycle_acquisition_candidate_binding_mismatch",
    ):
        await controller.run(_problem(), budget_state=_budget(), max_cycles=1)


@pytest.mark.asyncio
async def test_typed_value_world_knowledge_gap_routes_without_renaming_blocker() -> None:
    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        value_port=_WorldKnowledgeGapValuePort(),
    )

    run = await controller.run(_problem(), budget_state=_budget(), max_cycles=1)
    cycle = run.cycles[0]

    assert cycle.value_port.authority_blockers == ("treatment_assignment_not_owner_derived",)
    assert cycle.terminal_kind == "acquisition_required"
    assert cycle.revision_request.revision_strategy == "acquire_or_elicit"
    acquisition = cycle.revision_request.strategy_payload["acquisition_request"]
    assert acquisition["requirement_gap"]["requirement_gap_id"] == (
        "requirement-gap:data_requirement:value-input-world-knowledge"
    )
    assert acquisition["requirement_gap"]["metadata"]["satisfaction_status"] == ("unsatisfied")
    assert cycle.acquisition_routing_report is not None
    assert cycle.acquisition_receipt is None
    assert cycle.acquisition_routing_report.status == "pass"
    assert len(cycle.acquisition_routing_report.acquisition_records) == 1
    record = cycle.acquisition_routing_report.acquisition_records[0]
    assert record.compiled_requirement_ref == ("runtime-requirement:value-input-world-knowledge:v1")
    assert record.claim_ref == "value-claim:candidate_cgf_shadow"
    assert record.terminal_disposition.value == "acquire"


@pytest.mark.asyncio
async def test_k_sim_does_not_shrink_k_world() -> None:
    with pytest.raises(ValueError, match="k_sim_must_not_shrink_k_world"):
        _ShrinkingSimulationPort()(
            candidate=_Candidate(
                candidate_id="candidate_bad_sim",
                atom=_Atom("candidate_bad_sim", "sha256:" + "7" * 64),
                diversity_key=("grant", "firms", "sim", "bad"),
            ),
            problem=_problem(),
            cycle_index=0,
        )


@pytest.mark.asyncio
async def test_generation_cycle_contract_mutations_turn_red(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    census_count = 0
    collect_census = generation_cycle_module._collect_strangle_source_census

    def count_census(repo_root: Path) -> Any:
        nonlocal census_count
        census_count += 1
        return collect_census(repo_root)

    monkeypatch.setattr(
        generation_cycle_module,
        "_collect_strangle_source_census",
        count_census,
    )
    try:
        payload, replay_context = await contract._build_live_payload_in_verification_namespace(
            REPO_ROOT,
            state_root=tmp_path,
        )
    except contract._N6VerificationReplayUnavailableError as unavailable:
        # Preserve the two-cycle/12-mutation proof when the owner issues N9. The
        # current head has no appointed N9 issuer, so the honest result is a
        # typed UNRUN with zero callback/session activity, never synthetic green.
        measurement = unavailable.measurement
        if unavailable.code != "n9_final_problem_session_not_reached":
            pytest.fail(f"unexpected unavailable replay code: {unavailable.code}")
        assert measurement["status"] == "UNRUN"
        assert measurement["callback_attempt_count"] == 0
        assert measurement["session_open_count"] == 0
        assert measurement["n6_gate_observation"]["deployment_identity_status"] == "established"
        assert measurement["n6_gate_observation"]["promotion_port_reason"].startswith(
            "generation_cycle_n6_census_not_established:"
        )
        assert measurement["selector_denominator"]["n6_cycles"] > 0
        assert measurement["selector_denominator"]["n6_candidate_summaries"] > 0
        assert measurement["selector_denominator"]["n9_callback_attempt_count"] == 0
        assert measurement["selector_denominator"]["n9_candidate_summaries"] is None
        assert measurement["selector_denominator"]["candidate_ids"] is None
        assert measurement["selector_denominator"]["receipt_candidate_denominator_matches"] is None
        assert measurement["selector_denominator"]["comparison_admissions"] is None
        assert measurement["predicate_basis"]["final_problem_binding"].startswith("not_reached:")
        assert "N9 callback was not reached" in measurement["predicate"]
        return

    # This is the original positive semantic witness, retained for a head where
    # a real N9 owner callback becomes available.
    assert census_count == 1
    strangle_mutation = next(
        item
        for item in payload["behavioral_mutations"]
        if item["mutation_id"] == "single_pass_fixture_survives_as_production_cycle"
    )
    assert strangle_mutation["status"] == "red"
    assert "strangle_receipt_stale" in strangle_mutation["issue_codes"]
    report = contract.validate_payload(payload, repo_root=REPO_ROOT)
    assert census_count == 2

    assert report["status"] == "pass", report["issues"]
    assert len(replay_context.run.cycles) >= 2
    assert replay_context.callback_count == 1
    assert replay_context.session_open_count == 1
    assert replay_context.problem_binding == contract.N9DesignProblemBinding.from_problem(
        replay_context.problem
    )
    assert replay_context.risk_scope == contract.confidence_risk_scope_for_problem(
        replay_context.problem_binding
    )
    assert replay_context.session.risk_scope == replay_context.risk_scope
    run_candidate_ids = {
        summary.candidate_id for summary in replay_context.run.candidate_summaries
    }
    assert replay_context.session_factory.candidate_ids
    assert set(replay_context.session_factory.candidate_ids) <= run_candidate_ids
    initial_binding = contract.N9DesignProblemBinding.from_problem(contract._design_problem())
    assert replay_context.problem_binding.problem_content_hash != initial_binding.problem_content_hash
    assert len(replay_context.comparison_admissions) == len(
        replay_context.run.promotion_port.receipts
    )
    mutation_statuses = {
        item["mutation_id"]: item["status"] for item in payload["behavioral_mutations"]
    }
    assert mutation_statuses == {
        "revision_not_terminal_driven": "red",
        "retry_without_new_grammar_admitted": "red",
        "voi_scheduler_ignored_fixed_cycle_count": "red",
        "single_pass_fixture_survives_as_production_cycle": "red",
        "proxy_gap_candidate_promoted_without_adversarial_validate": "red",
        "decision_front_admitted_non_current_valid": "red",
        "grounding_bypassed_cgf_firewall": "red",
        "coverage_depends_on_llm": "red",
        "k_sim_shrank_k_world": "red",
        "full_denominator_curated_subset": "red",
        "incoherent_single_terminal_run": "red",
        "empty_cycle_run": "red",
    }
    assert payload["denominators"]["counts"] == {
        "front_kinds": 4,
        "grounding_dispositions": 5,
        "grounding_statuses": 5,
        "scheduling_actions": 4,
        "terminal_kinds": 12,
    }

def test_generation_cycle_contract_validator_fails_on_known_scope_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def known_scope_mismatch(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], object]:
        raise contract._N6VerificationReplayRaisedError(
            ValueError("confidence_ledger_scope_binding_mismatch"),
            {
                "callback_attempt_count": 1,
                "session_open_count": 1,
                "selector_denominator": {"candidate_summaries": 2, "promotion_receipts": 0},
            },
        )

    monkeypatch.setattr(
        contract,
        "_build_live_payload_in_verification_namespace",
        known_scope_mismatch,
    )
    monkeypatch.setattr(
        contract,
        "validate_payload",
        lambda _payload, **_kwargs: {"status": "pass", "issues": []},
    )
    report = contract._validate_committed_contract_text(REPO_ROOT, "{}")

    assert report["status"] == "fail"
    assert {
        "code": "confidence_ledger_scope_binding_mismatch",
        "stage": "live_n6_n9_replay",
    } in report["issues"]
    assert report["n9_replay_measurement"]["callback_attempt_count"] == 1
    assert report["n9_replay_measurement"]["selector_denominator"]["promotion_receipts"] == 0


def test_generation_cycle_contract_typed_inspection_failure_keeps_its_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def inspection_unavailable(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], object]:
        raise contract._N6InputInspectionUnavailableError(
            stage="test_input_read",
            error_type="PermissionError",
        )

    monkeypatch.setattr(
        contract,
        "_build_live_payload_in_verification_namespace",
        inspection_unavailable,
    )
    monkeypatch.setattr(
        contract,
        "validate_payload",
        lambda _payload, **_kwargs: {"status": "pass", "issues": []},
    )
    with pytest.raises(contract._N6InputInspectionUnavailableError) as raised:
        contract._validate_committed_contract_text(REPO_ROOT, "{}")
    assert raised.value.stage == "test_input_read"


def test_generation_cycle_contract_arbitrary_owner_oserror_is_fail_not_unrun(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def owner_io_defect(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], object]:
        raise OSError("owner predicate failed unexpectedly")

    monkeypatch.setattr(
        contract,
        "_build_live_payload_in_verification_namespace",
        owner_io_defect,
    )
    monkeypatch.setattr(
        contract,
        "validate_payload",
        lambda _payload, **_kwargs: {"status": "pass", "issues": []},
    )
    report = contract._validate_committed_contract_text(REPO_ROOT, "{}")

    assert report["status"] == "fail"
    assert report["issues"][-1]["code"] == "generation_cycle_contract_validator_error"
    assert report["predicate_result"] == "fail"


def test_generation_cycle_contract_unexpected_failure_is_fail_not_unrun(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unexpected_error(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], object]:
        raise NameError("unexpected checker defect")

    monkeypatch.setattr(
        contract,
        "_build_live_payload_in_verification_namespace",
        unexpected_error,
    )
    monkeypatch.setattr(
        contract,
        "validate_payload",
        lambda _payload, **_kwargs: {"status": "pass", "issues": []},
    )
    report = contract._validate_committed_contract_text(REPO_ROOT, "{}")

    assert report["status"] == "fail"
    assert report["issues"][-1]["code"] == "generation_cycle_contract_validator_error"
    assert report["predicate_result"] == "fail"


def test_generation_cycle_contract_one_shot_callback_reports_unrun_without_second_session_write(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    factory = contract._OneShotVerificationSessionFactory(REPO_ROOT, tmp_path / "session")
    problem = contract._design_problem()
    artifact_path = tmp_path / contract.OUTPUT_PATH
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text("{}", encoding="utf-8")

    def state_snapshot() -> tuple[list[str], dict[str, str]]:
        root = tmp_path / "session"
        directories = sorted(
            path.relative_to(tmp_path).as_posix() for path in root.rglob("*") if path.is_dir()
        )
        files = {
            path.relative_to(tmp_path).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*")
            if path.is_file()
        }
        return directories, files

    async def duplicate_callback(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], object]:
        factory(problem, ())
        before_second_attempt = state_snapshot()
        try:
            factory(problem, ())
        except contract._N6VerificationReplayUnavailableError as exc:
            error = exc
        else:  # pragma: no cover - a broken one-shot fence
            pytest.fail("second session callback unexpectedly succeeded")
        after_second_attempt = state_snapshot()
        assert before_second_attempt == after_second_attempt
        assert factory.callback_attempt_count == 2
        assert factory.session_open_count == 1
        raise contract._N6VerificationReplayRaisedError(
            error,
            contract._verification_session_factory_measurement(factory),
        )

    monkeypatch.setattr(
        contract,
        "_build_live_payload_in_verification_namespace",
        duplicate_callback,
    )
    monkeypatch.setattr(
        contract,
        "validate_payload",
        lambda _payload, **_kwargs: {"status": "pass", "issues": []},
    )

    exit_code = contract.main(
        ["--repo-root", str(tmp_path), "--check", "--output-format", "json"]
    )

    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert exit_code == 2
    assert report["status"] == "UNRUN"
    assert report["predicate_result"] == "not_run"
    assert report["issues"][0]["code"] == "verification_session_factory_reused"
    n9_measurement = report["measurement"]["selector_denominator"]["n6_n9_replay"]
    assert n9_measurement["callback_attempt_count"] == 2
    assert n9_measurement["session_open_count"] == 1
    assert "second callback predicate was not reached" in n9_measurement["predicate"]
    assert any(
        item.get("path") == contract.OUTPUT_PATH and item.get("status") == "read"
        for item in report["measurement"]["files"]["inputs"]
    )
    assert "Traceback" not in captured.out + captured.err


def test_generation_cycle_contract_cli_uses_exit_two_for_unrun(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / contract.OUTPUT_PATH
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text("seed", encoding="utf-8")
    read_text = Path.read_text

    def unreadable_input(path: Path, *args: Any, **kwargs: Any) -> str:
        if path == artifact_path:
            raise PermissionError("input is inaccessible")
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", unreadable_input)

    exit_code = contract.main(
        ["--repo-root", str(tmp_path), "--check", "--output-format", "text"]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "UNRUN layer3_gy_generation_cycle_contract" in captured.err
    assert "Measurement details:" in captured.err


def test_generation_cycle_contract_check_discloses_measured_inputs_and_n9_denominator(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / contract.OUTPUT_PATH
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_bytes((REPO_ROOT / contract.OUTPUT_PATH).read_bytes())

    exit_code = contract.main(
        ["--repo-root", str(tmp_path), "--check", "--output-format", "json"]
    )

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert report["status"] == "UNRUN"
    files = report["measurement"]["files"]
    assert files["complete_verdict"] is False
    assert files["finding_coverage"] == "explicit file-reader operations only"
    assert any(
        item.get("path") == contract.OUTPUT_PATH
        and item.get("operation") == "read_text"
        and item.get("status") == "read"
        for item in files["inputs"]
    )
    n9 = report["measurement"]["selector_denominator"]["n6_n9_replay"]
    assert n9["status"] == "not_reached"
    assert n9["callback_attempt_count"] == 0
    assert n9["session_open_count"] == 0
    assert n9["currentness"]["historical_replay"]["status"] == "pass"
    assert n9["selector_denominator"]["n9_candidate_summaries"] is None
    assert report["measurement"]["unresolved_by_construction"]


def test_generation_cycle_contract_write_refuses_when_n9_is_not_reached() -> None:
    """The write refuses to mint the artifact before the live N9 predicate is reached."""

    with pytest.raises(contract._N6VerificationReplayUnavailableError) as raised:
        contract.build_contract_json_for_write(REPO_ROOT)

    assert raised.value.code == "n9_final_problem_session_not_reached"
    assert raised.value.measurement["callback_attempt_count"] == 0


def test_generation_cycle_contract_owner_refuses_stale_comparison_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The frozen-contract owner refuses stale comparison identity independently of N9."""

    frozen = json.loads((REPO_ROOT / contract.OUTPUT_PATH).read_text(encoding="utf-8"))
    plan = contract.build_gy_comparison_projection_plan_from_manifest(
        frozen,
        manifest=frozen["comparison_admission_manifest"],
        owner_rule_registry=(
            contract.canonical_promotion_verification_comparison_owner_rule_registry()
        ),
    )
    live = copy.deepcopy(frozen)
    stale = copy.deepcopy(frozen)
    stale_manifest = stale["comparison_admission_manifest"]
    assert stale_manifest
    stale_manifest[0]["predicate_provenance"] = "not_established"
    stale["contract_content_hash"] = contract._contract_content_hash(stale)
    artifact_path = tmp_path / contract.OUTPUT_PATH
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(json.dumps(stale), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="generation_cycle_comparison_admission_manifest_drift",
    ):
        contract._reconcile_frozen_contract(tmp_path, live, plan)

    # Removal probe: with the owner comparison predicate removed, this stale
    # admission is accepted and rewritten under the live plan's identity.
    monkeypatch.setattr(
        contract,
        "_frozen_comparison_identity_admissible",
        lambda _frozen, _plan: True,
    )
    reconciled = contract._reconcile_frozen_contract(tmp_path, live, plan)
    assert reconciled["comparison_admission_manifest"] == plan.manifest


def test_generation_cycle_strangle_receipt_recomputes_production_callers() -> None:
    receipt = StrangleReceipt.recompute(REPO_ROOT)

    assert receipt.status == "strangled"
    assert receipt.production_single_pass_callers == ()
    assert receipt.default_cycle_controller.endswith("GenerationCycleController")
    assert not any(
        "src/polisyos/runtime/http/services/control/workspace_loop_transition.py" in caller
        for caller in receipt.allowed_fixture_callers
    )


def test_generation_cycle_strangle_receipt_counts_new_production_caller(tmp_path: Path) -> None:
    caller = (
        tmp_path
        / "src"
        / "polisyos"
        / "runtime"
        / "http"
        / "services"
        / "control"
        / "production_single_pass_probe.py"
    )
    caller.parent.mkdir(parents=True)
    caller.write_text(
        "def execute(loop):\n    return loop.run_fixture('ua_msme_credit_worldbank_measurement')\n",
        encoding="utf-8",
    )

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "drift"
    assert receipt.allowed_fixture_callers == ()
    assert receipt.production_single_pass_callers == (
        "src/polisyos/runtime/http/services/control/production_single_pass_probe.py:2",
    )


@pytest.mark.asyncio
async def test_n6_strangle_drift_is_distinguished_from_unknown_and_candidate_remains_available(
    tmp_path: Path,
) -> None:
    """Known source drift blocks authority; absent census evidence stays UNRUN."""

    run = await GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        value_port=_DataGapValuePort(),
        repo_root=tmp_path,
    ).run(_problem(), budget_state=_budget(), max_cycles=1)
    assert run.cycles
    assert run.candidate_summaries

    unknown_receipt = StrangleReceipt.recompute(tmp_path)
    assert unknown_receipt.status == "not_established"
    unknown_run = run.model_copy(update={"strangle_receipt": unknown_receipt})
    unknown_issues = generation_cycle_module._validate_generation_cycle_run_with_current_source_receipt(
        unknown_run,
        current_strangle_receipt=unknown_receipt,
    )
    unknown_codes = {issue["code"] for issue in unknown_issues}
    assert "strangle_receipt_not_established" in unknown_codes
    assert "single_pass_fixture_survives_as_production_cycle" not in unknown_codes
    assert "strangle_receipt_currentness_not_established" in unknown_codes
    assert validate_generation_cycle_candidate_run(unknown_run) == ()

    source = tmp_path / "src" / "polisyos" / "runtime" / "single_pass_probe.py"
    source.parent.mkdir(parents=True)
    marker_source = (
        "def execute(loop):\n"
        "    # run_fixture marker remains after removing the call\n"
        "    marker = 'run_fixture'\n"
        "    return loop.run_fixture('fixture_name')\n"
    )
    source.write_text(marker_source, encoding="utf-8")
    drift_receipt = StrangleReceipt.recompute(tmp_path)
    assert drift_receipt.status == "drift"
    drift_run = run.model_copy(update={"strangle_receipt": drift_receipt})
    drift_issues = generation_cycle_module._validate_generation_cycle_run_with_current_source_receipt(
        drift_run,
        current_strangle_receipt=drift_receipt,
    )
    drift_codes = {issue["code"] for issue in drift_issues}
    assert "single_pass_fixture_survives_as_production_cycle" in drift_codes
    assert "strangle_receipt_not_established" not in drift_codes
    # Candidate computation remains available; only strict authority is held.
    assert validate_generation_cycle_candidate_run(drift_run) == ()

    source.write_text(
        marker_source.replace("return loop.run_fixture('fixture_name')", "return None"),
        encoding="utf-8",
    )
    removed_property_receipt = StrangleReceipt.recompute(tmp_path)
    assert removed_property_receipt.status == "strangled"
    assert "run_fixture" in source.read_text(encoding="utf-8")
    removed_property_run = run.model_copy(
        update={"strangle_receipt": removed_property_receipt}
    )
    removed_property_issues = (
        generation_cycle_module._validate_generation_cycle_run_with_current_source_receipt(
            removed_property_run,
            current_strangle_receipt=removed_property_receipt,
        )
    )
    removed_property_codes = {issue["code"] for issue in removed_property_issues}
    assert "single_pass_fixture_survives_as_production_cycle" not in removed_property_codes
    assert "strangle_receipt_currentness_not_established" in removed_property_codes


def test_generation_cycle_strangle_receipt_rechecks_comment_edit_on_later_invocation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src" / "polisyos" / "runtime.py"
    source.parent.mkdir(parents=True)
    source.write_text("def run():\n    return None\n", encoding="utf-8")

    earlier = StrangleReceipt.recompute(tmp_path)
    source.write_text(
        "def run():\n    return None\n\n# harmless later source edit\n",
        encoding="utf-8",
    )
    later = StrangleReceipt.recompute(tmp_path)

    assert earlier.status == later.status == "strangled"
    assert earlier.source_content_hash != later.source_content_hash
    with pytest.raises(
        GenerationCycleError,
        match="generation_cycle_strangle_receipt_stale",
    ):
        earlier.verify_current(tmp_path)


def test_generation_cycle_contract_check_maps_temporary_workspace_oserror_to_unrun(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / contract.OUTPUT_PATH
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text("{}", encoding="utf-8")

    def unavailable_tempdir(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("temporary workspace unavailable")

    monkeypatch.setattr(contract, "TemporaryDirectory", unavailable_tempdir)
    monkeypatch.setattr(
        contract,
        "validate_payload",
        lambda _payload, **_kwargs: {"status": "pass", "issues": []},
    )
    monkeypatch.setattr(
        contract,
        "inspect_n6_source_census",
        lambda _repo_root: contract.N6SourceCensusGateResult(
            source_verdict="pass",
            denominator_file_count=1,
            denominator_complete=True,
            denominator_path_sha256="0" * 64,
            semantic_census_sha256="1" * 64,
            inputs={"source_scope": "src/polisyos"},
        ),
    )
    exit_code = contract.main(
        ["--repo-root", str(tmp_path), "--check", "--output-format", "json"]
    )

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert report["status"] == "UNRUN"
    assert report["measurement"]["command"]["selected_mode"] == "check"
    assert any(
        issue.get("code") == "generation_cycle_contract_inspection_workspace_unavailable"
        and issue.get("stage") == "gy-n6-committed-check-"
        for issue in report["issues"]
    )
    assert report["measurement"]["files"]["complete_verdict"] is False


@pytest.mark.parametrize(
    "scenario",
    ["normal_cleanup_failure", "exception_cleanup_failure", "successful_cleanup"],
)
def test_generation_cycle_contract_check_types_cleanup_and_preserves_evidence(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    scenario: str,
) -> None:
    artifact_path = tmp_path / contract.OUTPUT_PATH
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text("{}", encoding="utf-8")
    cleanup_calls: list[tuple[type[BaseException] | None, BaseException | None]] = []
    partial_measurement = {
        "callback_attempt_count": 1,
        "status": "partial",
        "selector_denominator": {"candidate_summaries": 2},
    }
    cleanup_fails = scenario != "successful_cleanup"

    class FakeTemporaryDirectory:
        def __enter__(self) -> str:
            return str(tmp_path)

        def __exit__(
            self,
            error_type: type[BaseException] | None,
            error: BaseException | None,
            _traceback: Any,
        ) -> bool:
            cleanup_calls.append((error_type, error))
            if cleanup_fails:
                raise OSError("temporary workspace cleanup failed")
            return False

    monkeypatch.setattr(
        contract,
        "TemporaryDirectory",
        lambda **_kwargs: FakeTemporaryDirectory(),
    )
    monkeypatch.setattr(
        contract,
        "validate_payload",
        lambda _payload, **_kwargs: {"status": "pass", "issues": []},
    )

    monkeypatch.setattr(
        contract,
        "inspect_n6_source_census",
        lambda _repo_root: contract.N6SourceCensusGateResult(
            source_verdict="pass",
            denominator_file_count=1,
            denominator_complete=True,
            denominator_path_sha256="0" * 64,
            semantic_census_sha256="1" * 64,
            inputs={"source_scope": "src/polisyos"},
        ),
    )

    primary: contract._N6VerificationReplayRaisedError | None = None
    if scenario == "exception_cleanup_failure":
        primary = contract._N6VerificationReplayRaisedError(
            ValueError("primary N9 replay failure"),
            partial_measurement,
        )

        def failing_inspection(_repo_root: Path, _text: str) -> dict[str, Any]:
            with contract._inspection_workspace("cleanup-exception-exit-"):
                raise primary

        monkeypatch.setattr(contract, "_validate_committed_contract_text", failing_inspection)
    else:

        async def live_payload(
            _repo_root: Path,
            *,
            state_root: Path,
        ) -> tuple[dict[str, Any], SimpleNamespace]:
            assert state_root == tmp_path
            return {}, SimpleNamespace(comparison_plan=object())

        monkeypatch.setattr(
            contract,
            "_build_live_payload_in_verification_namespace",
            live_payload,
        )
        monkeypatch.setattr(
            contract,
            "_verification_replay_measurement",
            lambda _context: partial_measurement,
        )
        monkeypatch.setattr(
            contract,
            "_canonical_contract_json",
            lambda _payload, **_kwargs: "{}",
        )

    exit_code = contract.main(
        ["--repo-root", str(tmp_path), "--check", "--output-format", "json"]
    )

    captured = capsys.readouterr()
    report = json.loads(captured.out)
    if scenario == "normal_cleanup_failure":
        assert exit_code == 2
        assert report["status"] == "UNRUN"
        assert report["issues"][0]["code"] == (
            "generation_cycle_contract_inspection_workspace_cleanup_unavailable"
        )
        assert report["issues"][0]["error_type"] == "OSError"
        assert report["measurement"]["selector_denominator"]["n6_n9_replay"] == (
            partial_measurement
        )
        assert cleanup_calls == [(None, None)]
        assert "Traceback" not in captured.out + captured.err
    elif scenario == "exception_cleanup_failure":
        assert exit_code == 2
        assert report["status"] == "UNRUN"
        assert report["measurement"]["selector_denominator"]["n6_n9_replay"] == (
            partial_measurement
        )
        assert report["inspection_failure"]["receipts"]["primary_failure"] == {
            "error_type": "_N6VerificationReplayRaisedError",
            "original_error_type": "ValueError",
        }
        assert cleanup_calls == [(type(primary), primary)]
        assert "Traceback" not in captured.out + captured.err
    else:
        assert exit_code == 0
        assert report["status"] == "pass"
        assert report["measurement"]["selector_denominator"]["n6_n9_replay"] == (
            partial_measurement
        )
        assert cleanup_calls == [(None, None)]


def test_generation_cycle_contract_validator_removal_probe_rejects_missing_run_with_markers(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    markers_only = {
        "schema_version": contract.GENERATION_CYCLE_CONTRACT_SCHEMA_VERSION,
        "contract_id": "policyos.runtime.generation_cycle_controller",
        "producer": "tools.quality.validation.check_layer3_gy_generation_cycle_contract",
        "denominators": contract._denominators(),
        "positive_gate": {"cycle_count": 2},
        "strangle_receipt": {"status": "strangled"},
        "behavioral_mutations": [
            {"mutation_id": mutation_id, "status": "red"}
            for mutation_id in contract._EXPECTED_MUTATION_IDS
        ],
        "fail_closed_probes": [{"status": "fail_closed"}],
    }
    markers_only["contract_content_hash"] = contract._contract_content_hash(markers_only)
    report = contract.validate_payload(markers_only, repo_root=REPO_ROOT)
    assert report["status"] == "fail"
    assert any(issue.get("code") == "generation_cycle_run_missing" for issue in report["issues"])

    artifact_path = tmp_path / contract.OUTPUT_PATH
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(json.dumps(markers_only), encoding="utf-8")
    exit_code = contract.main(
        ["--repo-root", str(tmp_path), "--check", "--output-format", "json"]
    )
    cli_report = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert cli_report["status"] == "fail"
    assert any(
        issue.get("code") == "generation_cycle_run_missing"
        for issue in cli_report["issues"]
    )


def test_generation_cycle_contract_validator_removal_probe_rejects_stale_factory_scope_at_real_cli_boundary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    original_run = contract.GenerationCycleController.run
    observed = {"mutation_applied": False}

    async def return_run_with_stale_factory_scope(
        controller: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        run = await original_run(controller, *args, **kwargs)
        promotion_port = controller._promotion_port
        factory = getattr(promotion_port, "_confidence_ledger_session_factory", None)
        if (
            factory is None
            or factory.callback_attempt_count == 0
            or factory.problem is None
            or factory.problem_binding is None
            or factory.session is None
        ):
            return run

        recomputed_binding = contract.N9DesignProblemBinding.from_problem(factory.problem)
        recomputed_scope = contract.confidence_risk_scope_for_problem(recomputed_binding)
        assert factory.problem_binding == recomputed_binding
        assert factory.risk_scope == recomputed_scope
        assert factory.session.risk_scope == recomputed_scope

        same_subject_prior_problem = contract._design_problem()
        stale_binding = contract.N9DesignProblemBinding.from_problem(same_subject_prior_problem)
        assert stale_binding.design_problem_id == recomputed_binding.design_problem_id
        assert stale_binding.problem_content_hash != recomputed_binding.problem_content_hash
        stale_scope = contract.confidence_risk_scope_for_problem(stale_binding)
        assert stale_scope != recomputed_scope

        # Corrupt only the retained basis after the real N9 owner consumed the
        # matching session. The callback/session markers remain present.
        factory.risk_scope = stale_scope
        assert factory.session.risk_scope == recomputed_scope
        observed["mutation_applied"] = True
        return run

    monkeypatch.setattr(
        contract.GenerationCycleController,
        "run",
        return_run_with_stale_factory_scope,
    )
    exit_code = contract.main(
        ["--repo-root", str(REPO_ROOT), "--check", "--output-format", "json"]
    )

    report = json.loads(capsys.readouterr().out)
    n9 = report["measurement"]["selector_denominator"]["n6_n9_replay"]
    if not observed["mutation_applied"]:
        # Currentness/source-census can legitimately stop before a real N9
        # session exists. Preserve the real CLI probe as typed UNRUN in that
        # case; do not manufacture a session or treat its markers as evidence.
        assert exit_code == 2
        assert report["status"] == "UNRUN"
        assert n9["callback_attempt_count"] == 0
        assert n9["session_open_count"] == 0
        assert n9["status"] == "not_reached"
        assert any(
            issue.get("code")
            in {
                "generation_cycle_currentness_reissue_required",
                "n6_source_census_not_established",
                "n9_final_problem_session_not_reached",
            }
            for issue in report["issues"]
        )
        return

    assert exit_code == 1
    assert report["status"] == "fail"
    assert any(
        issue.get("code") == "confidence_ledger_scope_binding_mismatch"
        for issue in report["issues"]
    )
    assert n9["session_matches_final_n9_risk_scope"] is False
    assert n9["callback_attempt_count"] == 1


@pytest.mark.parametrize(
    ("contract_text", "expected_issue"),
    [
        ("seed", "generation_cycle_contract_invalid_json"),
        ("[]", "generation_cycle_contract_object_invalid"),
        ('{"generation_cycle_run":{}}', "generation_cycle_run_invalid"),
    ],
)
def test_generation_cycle_contract_malformed_committed_input_returns_typed_fail(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    contract_text: str,
    expected_issue: str,
) -> None:
    artifact_path = tmp_path / contract.OUTPUT_PATH
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(contract_text, encoding="utf-8")

    exit_code = contract.main(
        ["--repo-root", str(tmp_path), "--check", "--output-format", "json"]
    )

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert report["status"] == "fail"
    assert report["predicate_result"] == "fail"
    assert any(issue.get("code") == expected_issue for issue in report["issues"])
    assert report["measurement"]["selector_denominator"]["n6_n9_replay"][
        "callback_attempt_count"
    ] == 0


def test_generation_cycle_contract_cli_reports_unrun_for_unavailable_n9_replay(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / contract.OUTPUT_PATH
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text("{}", encoding="utf-8")
    measurement = {
        "status": "UNRUN",
        "callback_attempt_count": 0,
        "session_open_count": 0,
        "predicate": "N9 callback was not reached",
        "selector_denominator": {"n9_candidate_summaries": None},
    }

    async def n9_unavailable(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], object]:
        raise contract._N6VerificationReplayUnavailableError(
            "n9_final_problem_session_not_reached",
            measurement,
        )

    monkeypatch.setattr(
        contract,
        "_build_live_payload_in_verification_namespace",
        n9_unavailable,
    )
    monkeypatch.setattr(
        contract,
        "validate_payload",
        lambda _payload, **_kwargs: {"status": "pass", "issues": []},
    )
    exit_code = contract.main(
        ["--repo-root", str(tmp_path), "--check", "--output-format", "json"]
    )

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert report["status"] == "UNRUN"
    assert report["predicate_result"] == "not_run"
    n9 = report["measurement"]["selector_denominator"]["n6_n9_replay"]
    assert n9["callback_attempt_count"] == 0
    assert n9["session_open_count"] == 0
    assert n9["selector_denominator"]["n9_candidate_summaries"] is None
    assert "N9 callback was not reached" in n9["predicate"]


def test_generation_cycle_contract_rederive_entrypoint_returns_typed_unrun(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    measurement = {
        "status": "UNRUN",
        "callback_attempt_count": 0,
        "predicate": "live N6 currentness was not established",
    }

    async def unavailable_live_payload(_repo_root: Path) -> dict[str, Any]:
        raise contract._N6VerificationReplayUnavailableError(
            "n9_final_problem_session_not_reached",
            measurement,
        )

    monkeypatch.setattr(contract, "build_live_payload", unavailable_live_payload)
    exit_code = contract.main(
        ["--repo-root", str(tmp_path), "--rederive-audit", "--output-format", "json"]
    )

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert report["status"] == "UNRUN"
    assert report["issues"][0]["code"] == "n9_final_problem_session_not_reached"
    assert report["n9_replay_measurement"] == measurement


@pytest.mark.asyncio
async def test_blocked_voi_action_does_not_enter_n9_promotion_owner(tmp_path: Path) -> None:
    class _PromotionSpyController(GenerationCycleController):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.promotion_calls = 0

        def decide_next_action(self, **kwargs: Any) -> Any:
            decision = super().decide_next_action(**kwargs)
            return decision.model_copy(
                update={"next_action": "blocked", "reason": "explicit_voi_block"}
            )

        def _promote_completed_generation(self, **kwargs: Any) -> Any:
            self.promotion_calls += 1
            return generation_cycle_module.PromotionPortObservation(
                status="not_promoted", reason="scratch_promotion_spy"
            )

    controller = _PromotionSpyController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_CurrentValidGrounding(),
        value_port=PendingN8ValuePort(),
        repo_root=tmp_path,
    )
    run = await controller.run(
        _problem(), budget_state=_budget(), min_cycles=2, max_cycles=3
    )
    # Put the owner-entry predicate first to identify the N9-boundary removal red.
    assert controller.promotion_calls == 0
    assert run.terminal_status == "blocked"
    assert run.promotion_port.status == "not_promoted"


@pytest.mark.asyncio
async def test_nonblocked_scheduler_stop_still_reaches_n9_owner(tmp_path: Path) -> None:
    class _PromotionSpyController(GenerationCycleController):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.promotion_calls = 0

        def decide_next_action(self, **kwargs: Any) -> Any:
            decision = super().decide_next_action(**kwargs)
            return decision.model_copy(
                update={"next_action": "stop", "reason": "ordinary_scheduler_stop"}
            )

        def _promote_completed_generation(self, **kwargs: Any) -> Any:
            self.promotion_calls += 1
            return generation_cycle_module.PromotionPortObservation(
                status="not_promoted", reason="scratch_promotion_spy"
            )

    controller = _PromotionSpyController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_CurrentValidGrounding(),
        value_port=PendingN8ValuePort(),
        repo_root=tmp_path,
    )
    run = await controller.run(
        _problem(), budget_state=_budget(), min_cycles=2, max_cycles=3
    )
    assert run.terminal_status == "completed"
    assert run.cycles[0].grounding.current_valid is True
    assert run.promotion_port.status == "not_promoted"
    assert controller.promotion_calls == 0
    assert run.cycles
    assert run.candidate_summaries
    assert run.promotion_port.reason == (
        "generation_cycle_n6_census_not_established:n6_census_issuer_not_appointed"
    )
    assert validate_generation_cycle_candidate_run(run) == ()
