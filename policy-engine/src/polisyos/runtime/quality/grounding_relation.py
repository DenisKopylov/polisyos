"""Shadow CGF relation certificates over the CG0 credal reference.

This module owns GY-CG1 only: it parses an N4 proposal into candidate
mechanistic hypotheses, retrieves reference-neighbour atoms from the full CG0
credal reference, checks joint typed cross-modal consistency with OR-Tools
CP-SAT, and emits a replayable ``GroundingRelationCertificate``. It does not
bind, admit, or promote candidates.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol

import duckdb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.credal_reference import (
    CredalReference,
    CredalReferenceEdge,
    EdgeKey,
    build_credal_reference,
)

if TYPE_CHECKING:
    from pathlib import Path

GROUNDING_RELATION_SCHEMA_VERSION = "policyos.runtime.grounding_relation_certificate.v1"
GROUNDING_RELATION_VALIDATOR_VERSION = "policyos.runtime.grounding_relation.cg1.v1"
NUMERIC_SCALING = "basis_points"

AxisRelation = Literal[
    "equivalent",
    "narrower",
    "broader",
    "overlap",
    "contradiction",
    "unknown",
]
SelectedRelation = Literal[
    "exact",
    "certified-specialization",
    "generalization",
    "partial",
    "compositional",
    "false-analog",
    "novel-candidate",
    "unknown",
    "blocked",
]
SolverStatus = Literal["SAT", "UNSAT", "UNKNOWN"]
RecommendedTransition = Literal[
    "shadow",
    "quarantine",
    "handoff_RT3",
    "bundle_bind-suggestion",
]

RELATION_UNIVERSE: tuple[SelectedRelation, ...] = (
    "exact",
    "certified-specialization",
    "generalization",
    "partial",
    "compositional",
    "false-analog",
    "novel-candidate",
    "unknown",
)
RELATION_AXES: tuple[str, ...] = (
    "op",
    "target",
    "do_value",
    "sign",
    "params",
    "unit",
    "scope",
    "population",
    "time",
    "outcome",
    "effect_path",
    "estimand",
    "admissibility",
    "wm_version",
)
CRITICAL_AXES: tuple[str, ...] = (
    "op",
    "target",
    "do_value",
    "sign",
    "scope",
    "population",
    "outcome",
    "effect_path",
    "estimand",
)
_SHADOW_TRANSITIONS = frozenset({"shadow", "quarantine", "handoff_RT3", "bundle_bind-suggestion"})
_BIND_TRANSITIONS = frozenset({"exact_bind", "bundle_bind", "promote", "admit"})
_UNKNOWN = "unknown"
_TOKEN_RE = re.compile(r"[a-zA-Z0-9_.-]+")


class _StrictModel(BaseModel):
    """Strict immutable base for CG1 runtime DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class AxisEntailmentWitness(_StrictModel):
    """One GY-K-style per-axis witness used as input, never as decider."""

    axis: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    witness: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)


class AxisWitnessProvider(Protocol):
    """Protocol for bounded gateway entailment witnesses."""

    def witness_axis(
        self,
        *,
        axis: str,
        proposal_value: object,
        atom_value: object,
    ) -> AxisEntailmentWitness:
        """Return a per-axis entailment witness."""


class MechanisticSignature(_StrictModel):
    """Causal-mechanistic signature denoting concrete do-query hypotheses."""

    op: str | None = None
    X_do: tuple[str, ...] = ()
    x_do: dict[str, Any] = Field(default_factory=dict)
    sign: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    scope: str | None = None
    unit: str | None = None
    population: str | None = None
    time: str | None = None
    outcome: tuple[str, ...] = ()
    effect_path: tuple[str, ...] = ()
    estimand: str | None = None
    admissibility: str | None = None
    wm_version: str | None = None
    evidence: tuple[str, ...] = ()
    modal_claims: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def denotation_key(self) -> dict[str, Any]:
        """Return the causal denotation fields used for exact/specialization."""

        return {
            "X_do": list(self.X_do),
            "effect_path": list(self.effect_path),
            "estimand": self.estimand,
            "op": self.op,
            "outcome": list(self.outcome),
            "population": self.population,
            "scope": self.scope,
            "sign": self.sign,
            "x_do": self.x_do,
        }


class ProposalHypothesis(_StrictModel):
    """One parsed proposal hypothesis from the open canonical AST."""

    hypothesis_id: str = Field(..., min_length=1)
    canonical_ast: dict[str, Any]
    signature: MechanisticSignature


class ParsedProposal(_StrictModel):
    """Open AST and hypothesis set parsed from an N4 proposal."""

    proposal_id: str = Field(..., min_length=1)
    raw_text: str = ""
    raw_text_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    canonical_ast: dict[str, Any]
    hypotheses: tuple[ProposalHypothesis, ...]


class GroundingCandidateAtom(_StrictModel):
    """Reference-derived atom candidate used by CG1 relation checking."""

    atom_id: str = Field(..., min_length=1)
    signature: MechanisticSignature
    edge_scope: tuple[str, ...] = ()
    reference_lift: dict[str, dict[str, Any]] = Field(default_factory=dict)
    retrieved_as_neighbor: bool = False
    retrieval_reasons: tuple[str, ...] = ()
    retrieval_score: float = Field(0.0, ge=0.0)
    is_adversarial_countercandidate: bool = False
    countercandidate_reason: str | None = None


class AxisRelationWitness(_StrictModel):
    """Sound witness for one RT1 axis relation."""

    axis: str = Field(..., min_length=1)
    relation: AxisRelation
    confidence: float = Field(..., ge=0.0, le=1.0)
    witness: str = Field(..., min_length=1)
    evidence_ref: str = Field(..., min_length=1)
    gy_k_witness: AxisEntailmentWitness | None = None


class CandidateRelationResult(_StrictModel):
    """Relation result for one hypothesis/candidate pair."""

    hypothesis_id: str = Field(..., min_length=1)
    atom_id: str = Field(..., min_length=1)
    selected_relation: SelectedRelation
    solver_status: SolverStatus
    axis_witnesses: tuple[AxisRelationWitness, ...]
    critical_contradictions: tuple[str, ...] = ()
    unresolved_axes: tuple[str, ...] = ()
    residual_constraints: tuple[str, ...] = ()
    unsat_core_if_any: tuple[str, ...] = ()
    retrieval_reasons: tuple[str, ...] = ()
    retrieval_score: float = Field(0.0, ge=0.0)


class GroundingEnginePolicy(_StrictModel):
    """Test-only mutation switches for P29 behavioral contract probes."""

    disable_alias_resolution: bool = False
    disable_adversarial_counter_family: bool = False
    disable_novel_candidate_verdict: bool = False
    allow_surface_similarity_exact: bool = False
    use_greedy_solver: bool = False
    disable_critical_veto: bool = False
    allow_gy_k_decider: bool = False
    allow_bind_recommendations: bool = False
    over_veto_unproven: bool = False


class GroundingRelationCertificate(_StrictModel):
    """Content-addressed CG1 shadow relation certificate."""

    schema_version: Literal["policyos.runtime.grounding_relation_certificate.v1"] = (
        GROUNDING_RELATION_SCHEMA_VERSION
    )
    certificate_id: str = Field(..., pattern=r"^cg1_cert_[a-f0-9]{16}$")
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    proposal_id: str = Field(..., min_length=1)
    raw_text_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    candidate_atom_ids: tuple[str, ...]
    proposal_signature: dict[str, Any]
    atom_signature_or_bundle: dict[str, Any]
    relation_set: dict[str, Any]
    selected_relation: SelectedRelation
    relation_confidence_scope: str = "symbolic_axis_witnesses_not_scalar_binding"
    reference_versions: dict[str, str]
    axis_witnesses: tuple[AxisRelationWitness, ...]
    critical_contradictions: tuple[str, ...] = ()
    unresolved_axes: tuple[str, ...] = ()
    residual_constraints: tuple[str, ...] = ()
    compositional_cover: dict[str, Any] | None = None
    cross_modal_witnesses: dict[str, Any]
    solver_status: SolverStatus
    unsat_core_if_any: tuple[str, ...] = ()
    recommended_transition: RecommendedTransition
    validator_version: str = GROUNDING_RELATION_VALIDATOR_VERSION
    stale_conditions: tuple[str, ...]
    shadow_only: bool = True
    no_bind_admit_promote: bool = True

    @model_validator(mode="after")
    def _shadow_only_boundary(self) -> GroundingRelationCertificate:
        if self.recommended_transition not in _SHADOW_TRANSITIONS:
            raise ValueError("cg1_recommended_transition_not_shadow_only")
        if self.recommended_transition in _BIND_TRANSITIONS:
            raise ValueError("cg1_bind_transition_forbidden")
        if not self.shadow_only or not self.no_bind_admit_promote:
            raise ValueError("cg1_shadow_only_flag_missing")
        return self


@dataclass(frozen=True)
class _SolverResult:
    status: SolverStatus
    unsat_core: tuple[str, ...] = ()
    cross_modal_witnesses: dict[str, Any] | None = None


@dataclass(frozen=True)
class _ProposalVerdict:
    selected_relation: SelectedRelation
    representative: CandidateRelationResult | None
    coverage_claim: dict[str, Any]


class GroundingRelationEngine:
    """Thin GY-CG1 engine over a CG0 ``CredalReference``."""

    def __init__(
        self,
        reference: CredalReference,
        *,
        axis_witness_provider: AxisWitnessProvider | None = None,
        policy: GroundingEnginePolicy | None = None,
    ) -> None:
        self.reference = reference
        self.axis_witness_provider = axis_witness_provider
        self.policy = policy or GroundingEnginePolicy()
        self._reference_atoms: tuple[GroundingCandidateAtom, ...] | None = None
        self._fts_index: _DuckDbReferenceFtsIndex | None = None

    @property
    def reference_atoms(self) -> tuple[GroundingCandidateAtom, ...]:
        """Return owner-derived L6/WMR atom candidates."""

        if self._reference_atoms is None:
            self._reference_atoms = tuple(_reference_atoms_from_cg0(self.reference))
        return self._reference_atoms

    def certificate_for(
        self,
        proposal: str | Mapping[str, Any] | BaseModel,
        *,
        proposal_id: str | None = None,
        include_adversarial_countercandidates: bool = True,
    ) -> GroundingRelationCertificate:
        """Return a deterministic shadow relation certificate for one proposal."""

        parsed = parse_n4_proposal(
            proposal,
            proposal_id=proposal_id,
            reference=self.reference,
            disable_alias_resolution=self.policy.disable_alias_resolution,
        )
        candidates = self.retrieve_candidates(
            parsed,
            include_adversarial_countercandidates=include_adversarial_countercandidates,
        )
        pair_results = self._candidate_relation_results(parsed, candidates)
        verdict = _proposal_verdict(
            pair_results,
            candidates=candidates,
            parsed=parsed,
            reference=self.reference,
            retrieval_indexed_edge_count=self._fts_index.indexed_edge_count
            if self._fts_index is not None
            else 0,
            policy=self.policy,
        )
        selected = verdict.representative
        if selected is None:
            selected_relation = verdict.selected_relation
            solver_status: SolverStatus = "SAT"
            axis_witnesses: tuple[AxisRelationWitness, ...] = ()
            critical: tuple[str, ...] = ()
            unresolved: tuple[str, ...] = ()
            residual: tuple[str, ...] = ()
            unsat_core: tuple[str, ...] = ()
        else:
            selected_relation = verdict.selected_relation
            solver_status = selected.solver_status
            axis_witnesses = selected.axis_witnesses
            critical = selected.critical_contradictions
            unresolved = selected.unresolved_axes
            residual = selected.residual_constraints
            unsat_core = selected.unsat_core_if_any
        recommended = _recommended_transition(
            selected_relation,
            allow_bind_recommendations=self.policy.allow_bind_recommendations,
        )
        raw_payload = {
            "candidate_atom_ids": [candidate.atom_id for candidate in candidates],
            "proposal_id": parsed.proposal_id,
            "raw_text_hash": parsed.raw_text_hash,
            "proposal_signature": _proposal_signature_payload(parsed),
            "atom_signature_or_bundle": _atom_signature_payload(candidates),
            "relation_set": _relation_set_payload(
                pair_results,
                candidates=candidates,
                coverage_claim=verdict.coverage_claim,
            ),
            "selected_relation": selected_relation,
            "reference_versions": dict(sorted(self.reference.component_versions.items())),
            "axis_witnesses": [item.model_dump(mode="json") for item in axis_witnesses],
            "critical_contradictions": list(critical),
            "unresolved_axes": list(unresolved),
            "residual_constraints": list(residual),
            "compositional_cover": None,
            "cross_modal_witnesses": _cross_modal_payload(
                pair_results,
                selected,
                gy_k_witness_mode=(
                    "provided_axis_witnesses"
                    if self.axis_witness_provider is not None
                    else "structural_only_no_runtime_gy_k_provider"
                ),
            ),
            "solver_status": solver_status,
            "unsat_core_if_any": list(unsat_core),
            "recommended_transition": recommended,
            "validator_version": GROUNDING_RELATION_VALIDATOR_VERSION,
            "stale_conditions": _stale_conditions(),
            "shadow_only": True,
            "no_bind_admit_promote": True,
        }
        content_hash = gy_content_hash(
            {
                "schema_version": GROUNDING_RELATION_SCHEMA_VERSION,
                **raw_payload,
            }
        )
        return GroundingRelationCertificate(
            certificate_id=f"cg1_cert_{content_hash.removeprefix('sha256:')[:16]}",
            content_hash=content_hash,
            **raw_payload,
        )

    def retrieve_candidates(
        self,
        parsed: ParsedProposal,
        *,
        include_adversarial_countercandidates: bool = True,
    ) -> tuple[GroundingCandidateAtom, ...]:
        """Retrieve high-recall candidates; retrieval never selects a relation."""

        if self._fts_index is None:
            self._fts_index = _DuckDbReferenceFtsIndex(self.reference)
        query = " ".join(
            [
                parsed.raw_text,
                *(
                    " ".join(_signature_text_terms(hypothesis.signature))
                    for hypothesis in parsed.hypotheses
                ),
            ]
        ).strip()
        lexical_hits = self._fts_index.search(query, limit=80)
        hit_keys = {hit["edge_key"] for hit in lexical_hits}
        hypothesis_tokens = _tokens(query)
        scored: dict[str, GroundingCandidateAtom] = {}
        for atom in self.reference_atoms:
            reasons: list[str] = []
            score = 0.0
            if set(atom.edge_scope) & hit_keys:
                reasons.append("lexical_duckdb_fts_full_cg0_reference")
                score += 0.35
            atom_tokens = _tokens(" ".join(_signature_text_terms(atom.signature)))
            token_overlap = len(hypothesis_tokens & atom_tokens)
            if token_overlap:
                reasons.append("l6_knob_wmr_token_overlap")
                score += min(0.35, 0.06 * token_overlap)
            if _has_l2_alignment_hint(parsed, atom):
                reasons.append("l2_variable_alignment_or_hierarchy")
                score += 0.12
            if _has_l3_or_l6_hint(parsed, atom):
                reasons.append("l3_threshold_or_l6_lex_map")
                score += 0.16
            if _has_causal_neighbourhood_hint(parsed, atom):
                reasons.append("causal_neighbourhood_skg")
                score += 0.10
            if reasons:
                scored[atom.atom_id] = atom.model_copy(
                    update={
                        "retrieved_as_neighbor": True,
                        "retrieval_reasons": tuple(sorted(set(reasons))),
                        "retrieval_score": round(min(score, 1.0), 6),
                    }
                )
        if not scored and self.reference_atoms:
            # Fail open for shadow analysis only: no candidate is never a safe bind.
            atom = self.reference_atoms[0]
            scored[atom.atom_id] = atom.model_copy(
                update={
                    "retrieved_as_neighbor": True,
                    "retrieval_reasons": ("coverage_floor_full_reference_seen",),
                    "retrieval_score": 0.01,
                }
            )
        candidates = tuple(
            sorted(
                scored.values(),
                key=lambda item: (
                    -item.retrieval_score,
                    grounding_candidate_semantic_sort_key(item),
                ),
            )
        )
        if (
            include_adversarial_countercandidates
            and not self.policy.disable_adversarial_counter_family
        ):
            candidates = (*candidates, *_adversarial_countercandidates(candidates, parsed))
        return candidates

    def _candidate_relation_results(
        self,
        parsed: ParsedProposal,
        candidates: Sequence[GroundingCandidateAtom],
    ) -> tuple[CandidateRelationResult, ...]:
        results: list[CandidateRelationResult] = []
        for hypothesis in parsed.hypotheses:
            solver = self._solve_joint_cross_modal(hypothesis)
            for candidate in candidates:
                if self.policy.allow_surface_similarity_exact and candidate.retrieval_score >= 0.8:
                    results.append(
                        CandidateRelationResult(
                            hypothesis_id=hypothesis.hypothesis_id,
                            atom_id=candidate.atom_id,
                            selected_relation="exact",
                            solver_status="SAT",
                            axis_witnesses=(),
                            retrieval_reasons=candidate.retrieval_reasons,
                            retrieval_score=candidate.retrieval_score,
                        )
                    )
                    continue
                if solver.status == "UNSAT":
                    results.append(
                        CandidateRelationResult(
                            hypothesis_id=hypothesis.hypothesis_id,
                            atom_id=candidate.atom_id,
                            selected_relation=(
                                "exact" if self.policy.use_greedy_solver else "blocked"
                            ),
                            solver_status=("SAT" if self.policy.use_greedy_solver else "UNSAT"),
                            axis_witnesses=(),
                            unsat_core_if_any=(
                                () if self.policy.use_greedy_solver else solver.unsat_core
                            ),
                            retrieval_reasons=candidate.retrieval_reasons,
                            retrieval_score=candidate.retrieval_score,
                        )
                    )
                    continue
                axis_witnesses = tuple(self._axis_witnesses(hypothesis.signature, candidate))
                relation = _relation_from_axes(
                    axis_witnesses,
                    candidate=candidate,
                    policy=self.policy,
                )
                results.append(
                    CandidateRelationResult(
                        hypothesis_id=hypothesis.hypothesis_id,
                        atom_id=candidate.atom_id,
                        selected_relation=relation,
                        solver_status=solver.status,
                        axis_witnesses=axis_witnesses,
                        critical_contradictions=tuple(
                            item.axis
                            for item in axis_witnesses
                            if item.axis in CRITICAL_AXES and item.relation == "contradiction"
                        ),
                        unresolved_axes=tuple(
                            item.axis for item in axis_witnesses if item.relation == "unknown"
                        ),
                        residual_constraints=tuple(_residual_constraints(axis_witnesses, relation)),
                        retrieval_reasons=candidate.retrieval_reasons,
                        retrieval_score=candidate.retrieval_score,
                    )
                )
        return tuple(results)

    def _solve_joint_cross_modal(self, hypothesis: ProposalHypothesis) -> _SolverResult:
        """Run the CP-SAT joint typed cross-modal consistency check."""

        if self.policy.use_greedy_solver:
            return _SolverResult(
                status="SAT",
                cross_modal_witnesses={
                    "solver": "greedy_mutation_probe",
                    "warning": "joint constraints bypassed",
                },
            )
        try:
            from ortools.sat.python import cp_model
        except ImportError:
            return _SolverResult(
                status="UNKNOWN",
                unsat_core=("ortools_cp_sat_unavailable",),
                cross_modal_witnesses={"solver": "ortools_cp_sat", "available": False},
            )

        claims = _compile_modal_claims(hypothesis.signature, self.reference)
        values_by_axis = _modal_axis_values(claims)
        model = cp_model.CpModel()
        z_vars: dict[str, dict[str, Any]] = {}
        for axis, values in sorted(values_by_axis.items()):
            if not values:
                continue
            z_vars[axis] = {
                value: model.NewBoolVar(f"z_{axis}_{_var_token(value)}") for value in sorted(values)
            }
            model.AddExactlyOne(z_vars[axis].values())

        assumptions: list[object] = []
        assumption_descriptions: dict[int, str] = {}

        def assume_constraint(description: str) -> object:
            literal = model.NewBoolVar(f"a_{len(assumptions)}")
            assumptions.append(literal)
            assumption_descriptions[literal.Index()] = description
            return literal

        for claim in claims:
            axis = claim["axis"]
            value = claim["value"]
            if axis not in z_vars:
                continue
            literal = assume_constraint(str(claim["description"]))
            model.Add(z_vars[axis][value] == 1).OnlyEnforceIf(literal)

        for description, ok in _hard_constraint_checks(hypothesis.signature, self.reference):
            literal = assume_constraint(description)
            if not ok:
                model.AddBoolOr([]).OnlyEnforceIf(literal)

        if assumptions:
            model.AddAssumptions(assumptions)
        score = model.NewIntVar(0, 10_000, "soft_score_basis_points")
        model.Add(score == _soft_score_basis_points(hypothesis.signature))
        model.Maximize(score)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 5.0
        status = solver.Solve(model)
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            return _SolverResult(
                status="SAT",
                cross_modal_witnesses={
                    "NL": _modal_claim_payload(claims, "NL"),
                    "L3": _modal_claim_payload(claims, "L3"),
                    "L6": _modal_claim_payload(claims, "L6"),
                    "do_AST": _modal_claim_payload(claims, "do_AST"),
                    "method": _modal_claim_payload(claims, "method"),
                    "numeric_scaling": NUMERIC_SCALING,
                    "solver": "ortools_cp_sat",
                    "soft_score_basis_points": int(solver.Value(score)),
                },
            )
        if status == cp_model.INFEASIBLE:
            core = tuple(
                assumption_descriptions.get(index, f"assumption_index:{index}")
                for index in solver.SufficientAssumptionsForInfeasibility()
            )
            return _SolverResult(
                status="UNSAT",
                unsat_core=core,
                cross_modal_witnesses={
                    "NL": _modal_claim_payload(claims, "NL"),
                    "L3": _modal_claim_payload(claims, "L3"),
                    "L6": _modal_claim_payload(claims, "L6"),
                    "do_AST": _modal_claim_payload(claims, "do_AST"),
                    "method": _modal_claim_payload(claims, "method"),
                    "numeric_scaling": NUMERIC_SCALING,
                    "solver": "ortools_cp_sat",
                    "unsat_core_kind": "SufficientAssumptionsForInfeasibility",
                },
            )
        return _SolverResult(
            status="UNKNOWN",
            unsat_core=("cp_sat_timeout_or_unknown",),
            cross_modal_witnesses={"solver": "ortools_cp_sat", "status": str(status)},
        )

    def _axis_witnesses(
        self,
        proposal: MechanisticSignature,
        candidate: GroundingCandidateAtom,
    ) -> list[AxisRelationWitness]:
        witnesses: list[AxisRelationWitness] = []
        for axis in RELATION_AXES:
            p_value = _axis_value(proposal, axis)
            a_value = _axis_value(candidate.signature, axis)
            relation, text = _axis_relation(
                axis,
                p_value,
                a_value,
                disable_alias_resolution=self.policy.disable_alias_resolution,
            )
            gy_k = None
            if self.axis_witness_provider is not None:
                gy_k = self.axis_witness_provider.witness_axis(
                    axis=axis,
                    proposal_value=p_value,
                    atom_value=a_value,
                )
            if self.policy.allow_gy_k_decider and gy_k is not None and gy_k.confidence >= 0.95:
                relation = "equivalent"
                text = f"mutated_gy_k_confidence_overrode_axis:{gy_k.confidence}"
            witnesses.append(
                AxisRelationWitness(
                    axis=axis,
                    relation=relation,
                    confidence=_axis_confidence(relation),
                    witness=text,
                    evidence_ref=_axis_evidence_ref(candidate, axis),
                    gy_k_witness=gy_k,
                )
            )
        return witnesses


def build_grounding_relation_certificate(
    proposal: str | Mapping[str, Any] | BaseModel,
    *,
    repo_root: Path | None = None,
    reference: CredalReference | None = None,
    proposal_id: str | None = None,
    axis_witness_provider: AxisWitnessProvider | None = None,
) -> GroundingRelationCertificate:
    """Build a CG1 shadow certificate from a proposal and CG0 reference."""

    if reference is None:
        if repo_root is None:
            msg = "repo_root_or_reference_required"
            raise ValueError(msg)
        reference = build_credal_reference(repo_root)
    engine = GroundingRelationEngine(
        reference,
        axis_witness_provider=axis_witness_provider,
    )
    return engine.certificate_for(proposal, proposal_id=proposal_id)


def parse_n4_proposal(
    proposal: str | Mapping[str, Any] | BaseModel,
    *,
    proposal_id: str | None = None,
    reference: CredalReference | None = None,
    disable_alias_resolution: bool = False,
) -> ParsedProposal:
    """Parse a raw/N4 proposal into an open AST plus hypothesis set."""

    raw_payload = proposal.model_dump(mode="json") if isinstance(proposal, BaseModel) else proposal
    if isinstance(raw_payload, Mapping):
        raw_text = _raw_text_from_mapping(raw_payload)
        signature = _signature_from_mapping(
            raw_payload,
            reference=reference,
            disable_alias_resolution=disable_alias_resolution,
        )
        explicit_id = _text(
            raw_payload.get("candidate_id")
            or raw_payload.get("proposal_id")
            or raw_payload.get("id")
        )
    else:
        raw_text = str(raw_payload)
        signature = _signature_from_text(
            raw_text,
            reference=reference,
            disable_alias_resolution=disable_alias_resolution,
        )
        explicit_id = ""
    raw_text_hash = gy_content_hash(raw_text)
    pid = proposal_id or explicit_id or f"proposal_{raw_text_hash.removeprefix('sha256:')[:16]}"
    canonical_ast = {
        "ast_kind": "cg1_open_mechanistic_proposal",
        "hypothesis_count": 1,
        "raw_text_hash": raw_text_hash,
        "source": "N4_proposal_or_stress_probe",
    }
    hypothesis_id = f"{pid}:h0"
    return ParsedProposal(
        proposal_id=pid,
        raw_text=raw_text,
        raw_text_hash=raw_text_hash,
        canonical_ast=canonical_ast,
        hypotheses=(
            ProposalHypothesis(
                hypothesis_id=hypothesis_id,
                canonical_ast={
                    "do_query_denotation": signature.denotation_key(),
                    "modal_claims": signature.modal_claims,
                    "open_ast": True,
                },
                signature=signature,
            ),
        ),
    )


class _DuckDbReferenceFtsIndex:
    """DuckDB FTS index over every CG0 essential edge."""

    def __init__(self, reference: CredalReference) -> None:
        self.reference = reference
        self.indexed_edge_count = len(reference.essential_edges)
        self._con: duckdb.DuckDBPyConnection | None = None

    def search(self, query: str, *, limit: int) -> list[dict[str, Any]]:
        """Return lexical full-reference FTS hits."""

        if not query.strip():
            return []
        if self._con is None:
            self._build()
        con = self._con
        if con is None:
            raise RuntimeError("duckdb_fts_index_not_initialized")
        safe_query = " ".join(sorted(_tokens(query)))[:800]
        if not safe_query:
            return []
        rows = con.execute(
            """
            SELECT doc_id, modality, edge_id,
                   fts_main_cg0_reference_edges.match_bm25(doc_id, ?) AS score
            FROM cg0_reference_edges
            WHERE score IS NOT NULL
            ORDER BY score DESC, doc_id
            LIMIT ?
            """,
            [safe_query, int(limit)],
        ).fetchall()
        return [
            {
                "edge_key": _edge_key_text((str(row[1]), str(row[2]))),
                "score": float(row[3] or 0.0),
            }
            for row in rows
        ]

    def _build(self) -> None:
        import pandas as pd

        con = duckdb.connect(":memory:")
        docs = {
            "doc_id": [],
            "edge_id": [],
            "modality": [],
            "text": [],
        }
        for edge in self.reference.essential_edges.values():
            docs["doc_id"].append(_edge_key_text(edge.key))
            docs["modality"].append(edge.modality)
            docs["edge_id"].append(edge.edge_id)
            docs["text"].append(_edge_search_text(edge))
        con.register("cg0_reference_edge_rows", pd.DataFrame(docs))
        con.execute(
            """
            CREATE TABLE cg0_reference_edges AS
            SELECT doc_id, modality, edge_id, text FROM cg0_reference_edge_rows
            """
        )
        con.execute("PRAGMA create_fts_index('cg0_reference_edges', 'doc_id', 'text')")
        self._con = con


def _reference_atoms_from_cg0(reference: CredalReference) -> list[GroundingCandidateAtom]:
    op_edges = {
        edge.edge_id: edge
        for edge in reference.essential_edges.values()
        if edge.modality == "L6_KNOB_OPERATOR"
    }
    target_edges = {
        edge.edge_id: edge
        for edge in reference.essential_edges.values()
        if edge.modality == "L6_KNOB_WORLD_SLOT"
    }
    lex_edges_by_knob: dict[str, list[CredalReferenceEdge]] = defaultdict(list)
    for edge in reference.essential_edges.values():
        if edge.modality != "L6_LEX_INTERVENTION_MAP":
            continue
        for completion in edge.admissible_completions:
            knob_id = _text(completion.value.get("knob_id"))
            if knob_id:
                lex_edges_by_knob[knob_id].append(edge)
    atoms: list[GroundingCandidateAtom] = []
    writable_slots = _writable_wmr_slots(reference)
    for op_id, op_edge in sorted(op_edges.items()):
        target_edge = target_edges.get(op_id)
        op_value = _first_completion_value(op_edge)
        target_value = _first_completion_value(target_edge) if target_edge is not None else {}
        explicit_slots = tuple(_string_list(target_value.get("target_world_slots")))
        domain = _mapping(op_value.get("parameter_domain"))
        target_slots = tuple(
            slot
            for slot in writable_slots
            if _operator_target_compatible(
                reference,
                op_id=op_id,
                domain=domain,
                target_slot=slot,
                explicit_slots=explicit_slots,
            )
        )
        for target_slot in target_slots:
            wmr_edges = _wmr_edges_for_target(reference, target_slot)
            edge_scope = [
                _edge_key_text(op_edge.key),
                *([_edge_key_text(target_edge.key)] if target_edge is not None else []),
                *(_edge_key_text(edge.key) for edge in lex_edges_by_knob.get(op_id, [])),
                *(_edge_key_text(edge.key) for edge in wmr_edges),
            ]
            edge_scope = sorted(set(edge_scope))
            scope_statuses = reference.reference_lift(edge_scope)
            all_confirmed = all(
                item.get("status") == "confirmed" for item in scope_statuses.values()
            )
            default_outcome = _default_outcome_for_target(target_slot)
            signature = MechanisticSignature(
                op=_canonical_operator(op_id),
                X_do=(target_slot,),
                x_do={"domain": domain},
                sign=_default_sign_for_operator(op_id),
                params={"domain": domain},
                scope=_scope_for_slot(target_slot),
                unit=_unit_for_target(reference, target_slot) or _text(domain.get("unit")) or None,
                population=_population_for_slot(target_slot),
                time="current_reference_epoch",
                outcome=default_outcome,
                effect_path=(op_id, target_slot, *default_outcome),
                estimand="average_treatment_effect",
                admissibility="passed" if all_confirmed else "reference_contested",
                wm_version=reference.component_versions.get("WMR"),
                evidence=tuple(edge_scope),
                modal_claims={
                    "L6": {"op": op_id, "target": target_slot, "knob": op_id},
                    "WMR": {"target": target_slot},
                    "CG1": {
                        "atom_universe_basis": "l6_operator_x_compatible_writable_wmr_slot",
                        "explicit_knob_world_slot": target_slot in explicit_slots,
                    },
                },
            )
            atom_hash = gy_content_hash(
                {
                    "edge_scope": sorted(edge_scope),
                    "signature": signature.model_dump(mode="json"),
                }
            )
            atoms.append(
                GroundingCandidateAtom(
                    atom_id=f"cg0_atom_{atom_hash.removeprefix('sha256:')[:16]}",
                    signature=signature,
                    edge_scope=tuple(sorted(set(edge_scope))),
                    reference_lift=scope_statuses,
                )
            )
    return atoms


def _signature_from_mapping(
    payload: Mapping[str, Any],
    *,
    reference: CredalReference | None,
    disable_alias_resolution: bool,
) -> MechanisticSignature:
    if "signature" in payload and isinstance(payload["signature"], Mapping):
        return _signature_from_explicit(
            payload["signature"],
            reference=reference,
            disable_alias_resolution=disable_alias_resolution,
        )
    atom = payload.get("atom") if isinstance(payload.get("atom"), Mapping) else payload
    if isinstance(atom, Mapping) and "operator_kind" in atom and "target_world_slots" in atom:
        return _signature_from_intervention_atom(
            atom,
            reference=reference,
            disable_alias_resolution=disable_alias_resolution,
        )
    raw_text = _raw_text_from_mapping(payload)
    return _signature_from_text(
        raw_text,
        reference=reference,
        disable_alias_resolution=disable_alias_resolution,
    )


def _signature_from_explicit(
    payload: Mapping[str, Any],
    *,
    reference: CredalReference | None,
    disable_alias_resolution: bool,
) -> MechanisticSignature:
    op = _text(payload.get("op")) or None
    if op and not disable_alias_resolution:
        op = _canonical_operator(op)
    raw_target = payload.get("X_do") or payload.get("target")
    target = tuple(_string_list(raw_target))
    if not target and isinstance(raw_target, str) and _text(raw_target):
        target = (_text(raw_target),)
    outcome = tuple(_string_list(payload.get("outcome")))
    modal_claims = (
        payload.get("modal_claims") if isinstance(payload.get("modal_claims"), Mapping) else {}
    )
    return MechanisticSignature(
        op=op,
        X_do=target,
        x_do=dict(_mapping(payload.get("x_do"))),
        sign=_canonical_sign(_text(payload.get("sign"))) or None,
        params=dict(_mapping(payload.get("params"))),
        scope=_text(payload.get("scope")) or _scope_for_slot(target[0]) if target else None,
        unit=_text(payload.get("unit"))
        or (_unit_for_target(reference, target[0]) if reference and target else None),
        population=_text(payload.get("population"))
        or (_population_for_slot(target[0]) if target else None),
        time=_text(payload.get("time")) or None,
        outcome=outcome,
        effect_path=tuple(_string_list(payload.get("effect_path"))),
        estimand=_canonical_estimand(_text(payload.get("estimand"))) or None,
        admissibility=_text(payload.get("admissibility")) or "candidate_unverified",
        wm_version=_text(payload.get("wm_version"))
        or (reference.component_versions.get("WMR") if reference else None),
        evidence=tuple(_string_list(payload.get("evidence"))),
        modal_claims={str(key): dict(_mapping(value)) for key, value in modal_claims.items()},
    )


def _signature_from_intervention_atom(
    atom: Mapping[str, Any],
    *,
    reference: CredalReference | None,
    disable_alias_resolution: bool,
) -> MechanisticSignature:
    operator_payload = _mapping(atom.get("operator_kind"))
    raw_op = _text(operator_payload.get("trinity_kind") or atom.get("operator_kind"))
    op = raw_op if disable_alias_resolution else _canonical_operator(raw_op)
    targets = tuple(_string_list(atom.get("target_world_slots")))
    direct = _mapping(atom.get("direct_effect_bundle"))
    do_expr = _mapping(atom.get("causal_do_expr"))
    estimand = _mapping(atom.get("intended_downstream_estimand"))
    assignments = _mapping_list(do_expr.get("assignments"))
    x_do = {
        _text(item.get("variable")): item.get("value")
        if item.get("value") is not None
        else item.get("value_expr")
        for item in assignments
        if _text(item.get("variable"))
    }
    if not x_do:
        x_do = {"target": list(targets), "params": dict(_mapping(direct.get("params")))}
    outcome = tuple(_string_list(estimand.get("outcome_variables")))
    functional = _canonical_estimand(_text(estimand.get("functional"))) or _text(
        estimand.get("target_kind")
    )
    return MechanisticSignature(
        op=op or None,
        X_do=targets,
        x_do=x_do,
        sign=_sign_from_params(_mapping(direct.get("params"))) or _default_sign_for_operator(op),
        params=dict(_mapping(direct.get("params"))),
        scope=_scope_from_atom(atom) or (targets and _scope_for_slot(targets[0])),
        unit=_text(estimand.get("unit_id"))
        or (_unit_for_target(reference, targets[0]) if reference and targets else None),
        population=_text(estimand.get("target_population"))
        or _text(_mapping(atom.get("target_selector")).get("target_population_type"))
        or (targets and _population_for_slot(targets[0])),
        time=_schedule_text(_mapping(direct.get("schedule"))),
        outcome=outcome,
        effect_path=(_text(direct.get("mechanism_id")) or raw_op, *targets),
        estimand=functional or None,
        admissibility=_text(atom.get("status")) or "candidate_unverified",
        wm_version=_text(atom.get("world_model_record_ref"))
        or (reference.component_versions.get("WMR") if reference else None),
        evidence=tuple(
            item
            for item in (
                _text(atom.get("content_hash")),
                *_string_list(atom.get("provenance_refs")),
            )
            if item
        ),
        modal_claims={
            "NL": {
                "op": op,
                "target": targets[0] if targets else "",
                "outcome": outcome[0] if outcome else "",
                "estimand": functional,
            },
            "L6": {"op": op, "target": targets[0] if targets else ""},
            "do_AST": {
                "op": op,
                "target": targets[0] if targets else "",
                "do_value": x_do,
            },
            "method": {
                "treatment_op": op,
                "treatment_target": targets[0] if targets else "",
                "outcome": outcome[0] if outcome else "",
                "estimand": functional,
            },
        },
    )


def _signature_from_text(
    text: str,
    *,
    reference: CredalReference | None,
    disable_alias_resolution: bool,
) -> MechanisticSignature:
    lower = text.casefold()
    op = _operator_from_text(lower)
    if op and not disable_alias_resolution:
        op = _canonical_operator(op)
    target = _target_from_text(lower)
    outcome = _outcome_from_text(lower, target)
    estimand = _estimand_from_text(lower)
    params = _params_from_text(lower)
    sign = _sign_from_text(lower) or _default_sign_for_operator(op)
    law_token = _law_token_from_text(lower)
    knob = _knob_from_text(lower)
    method_target = _method_target_from_text(lower) or target
    method_op = _method_operator_from_text(lower) or op
    modal_claims: dict[str, dict[str, Any]] = {
        "NL": {
            "op": op or "",
            "target": target or "",
            "outcome": outcome or "",
            "estimand": estimand or "",
        },
        "do_AST": {
            "op": op or "",
            "target": _do_target_from_text(lower) or target or "",
            "do_value": params,
        },
        "method": {
            "treatment_op": method_op or "",
            "treatment_target": method_target or "",
            "outcome": _method_outcome_from_text(lower) or outcome or "",
            "estimand": _method_estimand_from_text(lower) or estimand or "",
        },
    }
    if law_token:
        modal_claims["L3"] = {"law_token": law_token}
    if knob:
        modal_claims["L6"] = {"knob": knob}
    targets = (target,) if target else ()
    return MechanisticSignature(
        op=op or None,
        X_do=targets,
        x_do=params,
        sign=sign,
        params=params,
        scope=_scope_from_text(lower) or (_scope_for_slot(target) if target else None),
        unit=_unit_from_text(lower)
        or (_unit_for_target(reference, target) if reference and target else None),
        population=_population_from_text(lower)
        or (_population_for_slot(target) if target else None),
        time="proposal_current",
        outcome=(outcome,) if outcome else (),
        effect_path=tuple(item for item in (op, target, outcome) if item),
        estimand=estimand,
        admissibility="candidate_unverified",
        wm_version=reference.component_versions.get("WMR") if reference else None,
        evidence=(gy_content_hash(text),),
        modal_claims=modal_claims,
    )


def _compile_modal_claims(
    signature: MechanisticSignature,
    reference: CredalReference,
) -> list[dict[str, str]]:
    claims: list[dict[str, str]] = []

    def add(modality: str, axis: str, value: object, description: str) -> None:
        text = _canonical_axis_value(axis, value)
        if text and text != _UNKNOWN:
            claims.append(
                {
                    "axis": axis,
                    "description": f"{modality}.{description} == {text}",
                    "modality": modality,
                    "value": text,
                }
            )

    for modality, raw_fields in sorted(signature.modal_claims.items()):
        fields = _mapping(raw_fields)
        add(modality, "op", fields.get("op") or fields.get("treatment_op"), "op")
        add(modality, "target", fields.get("target") or fields.get("treatment_target"), "target")
        add(modality, "outcome", fields.get("outcome"), "outcome")
        add(modality, "estimand", fields.get("estimand"), "estimand")
        law_token = _text(fields.get("law_token"))
        if law_token:
            for op, target in _law_token_operator_targets(reference, law_token):
                add("L3", "op", op, f"law_token:{law_token}.operator")
                if target:
                    add("L3", "target", target, f"law_token:{law_token}.target")
        knob = _text(fields.get("knob"))
        if knob:
            target = _knob_target(reference, knob)
            add("L6", "op", knob, f"knob:{knob}.operator")
            if target:
                add("L6", "target", target, f"knob:{knob}.target")
    if signature.op:
        add("signature", "op", signature.op, "op")
    if signature.X_do:
        add("signature", "target", signature.X_do[0], "target")
    if signature.outcome:
        add("signature", "outcome", signature.outcome[0], "outcome")
    if signature.estimand:
        add("signature", "estimand", signature.estimand, "estimand")
    return claims


def _modal_axis_values(claims: Sequence[Mapping[str, str]]) -> dict[str, set[str]]:
    values: dict[str, set[str]] = defaultdict(set)
    for claim in claims:
        axis = str(claim["axis"])
        value = str(claim["value"])
        values[axis].add(value)
    return values


def _hard_constraint_checks(
    signature: MechanisticSignature,
    reference: CredalReference,
) -> list[tuple[str, bool]]:
    checks: list[tuple[str, bool]] = []
    target = signature.X_do[0] if signature.X_do else ""
    op = signature.op or ""
    if target:
        checks.append(
            (f"slot_exists({target}, {reference.reference_epoch})", _slot_exists(reference, target))
        )
        if (
            op
            and target
            and _knob_exists(reference, op)
            and _signature_claims_l6_knob(signature, op)
        ):
            checks.append(
                (f"allowed_target_type({op}, {target})", _knob_maps_to(reference, op, target))
            )
            checks.append((f"knob_maps_to({op}, {target})", _knob_maps_to(reference, op, target)))
    if op and _knob_exists(reference, op):
        checks.append(
            (
                f"params_in_operator_schema({op})",
                _params_in_operator_schema(reference, op, signature.params),
            )
        )
        checks.append(
            (
                f"threshold_satisfied({op})",
                _params_in_operator_schema(reference, op, signature.params),
            )
        )
    if target:
        checks.append(
            (
                f"unit_compatible({signature.unit or 'unitless'}, {target})",
                _unit_compatible(reference, target, signature.unit),
            )
        )
    for modality, fields in sorted(signature.modal_claims.items()):
        raw = _mapping(fields)
        law_token = _text(raw.get("law_token"))
        if law_token:
            checks.append(
                (
                    f"lex_applicable({law_token})",
                    bool(_law_token_operator_targets(reference, law_token)),
                )
            )
        method_target = _text(raw.get("treatment_target"))
        if modality == "method" and method_target and target:
            checks.append(
                (f"method.treatment == do_AST({method_target}, {target})", method_target == target)
            )
        method_outcome = _text(raw.get("outcome"))
        if modality == "method" and method_outcome and signature.outcome:
            checks.append(
                (
                    f"method.outcome in effect_bundle({method_outcome})",
                    method_outcome in signature.outcome,
                )
            )
    if signature.admissibility:
        checks.append(
            ("admissibility_passed_or_candidate_shadow", signature.admissibility != "failed")
        )
    checks.append((f"version_current({reference.reference_epoch})", True))
    return checks


def _signature_claims_l6_knob(signature: MechanisticSignature, op: str) -> bool:
    for modality, fields in sorted(signature.modal_claims.items()):
        if modality != "L6":
            continue
        raw = _mapping(fields)
        knob = _canonical_operator(raw.get("knob"))
        if knob and knob == _canonical_operator(op):
            return True
    return False


def _axis_relation(
    axis: str,
    proposal: object,
    atom: object,
    *,
    disable_alias_resolution: bool = False,
) -> tuple[AxisRelation, str]:
    if disable_alias_resolution and axis in {"op", "effect_path"}:
        p = _exact_axis_value(axis, proposal)
        a = _exact_axis_value(axis, atom)
    else:
        p = _canonical_axis_value(axis, proposal)
        a = _canonical_axis_value(axis, atom)
    if not p or not a or p == _UNKNOWN or a == _UNKNOWN:
        return "unknown", f"{axis}: unresolved proposal={p or _UNKNOWN} atom={a or _UNKNOWN}"
    if p == a:
        return "equivalent", f"{axis}: canonical values match ({p})"
    if axis == "target":
        p_set = {
            _canonical_variable(item)
            for item in _string_list(proposal)
            if _canonical_variable(item)
        }
        a_set = {
            _canonical_variable(item) for item in _string_list(atom) if _canonical_variable(item)
        }
        if p_set and a_set:
            if p_set == a_set:
                return "equivalent", f"{axis}: target sets match"
            if p_set.issubset(a_set):
                return "narrower", f"{axis}: proposal target subset of atom target"
            if a_set.issubset(p_set):
                return "broader", f"{axis}: proposal target broader than atom target"
            if p_set & a_set:
                return "overlap", f"{axis}: target sets overlap"
            return (
                "contradiction",
                f"{axis}: disjoint target slots {sorted(p_set)} vs {sorted(a_set)}",
            )
    if axis in {"sign", "do_value"} and _opposite_signs(p, a):
        return "contradiction", f"{axis}: opposite intervention direction {p} vs {a}"
    if axis == "do_value":
        if _concrete_params_conflict(proposal, atom):
            return "contradiction", "do_value: concrete do-values are incompatible"
        if _param_subset(proposal, atom):
            return "narrower", "do_value: proposal concrete value is inside atom do-domain"
        if _param_subset(atom, proposal):
            return "broader", "do_value: atom concrete value is inside proposal do-domain"
        if _params_overlap(proposal, atom):
            return "overlap", "do_value: do-value domains overlap"
        return "unknown", "do_value: no proven do-value contradiction"
    if axis == "effect_path":
        p_set = {
            _canonical_path_component(item)
            for item in _string_list(proposal)
            if _canonical_path_component(item)
        }
        a_set = {
            _canonical_path_component(item)
            for item in _string_list(atom)
            if _canonical_path_component(item)
        }
        if p_set and a_set and p_set.issubset(a_set):
            return "narrower", "effect_path: proposal path is covered by atom path"
        if p_set and a_set and a_set.issubset(p_set):
            return "broader", "effect_path: atom path is covered by proposal path"
    if axis in {"scope", "population"}:
        narrower = _narrower_scope(p, a)
        if narrower:
            return "narrower", f"{axis}: {p} is narrower than {a}"
        broader = _narrower_scope(a, p)
        if broader:
            return "broader", f"{axis}: {p} is broader than {a}"
    if axis == "params":
        if _concrete_params_conflict(proposal, atom):
            return "contradiction", "params: concrete parameter values are incompatible"
        if _param_subset(proposal, atom):
            return "narrower", "params: proposal concrete value is inside atom parameter domain"
        if _param_subset(atom, proposal):
            return "broader", "params: atom concrete value is inside proposal parameter domain"
        if _params_overlap(proposal, atom):
            return "overlap", "params: parameter domains overlap"
        return "contradiction", "params: parameter values/domains are incompatible"
    if axis == "unit" and _unit_alias(p) == _unit_alias(a):
        return "equivalent", f"{axis}: unit aliases match"
    if axis in CRITICAL_AXES:
        return "contradiction", f"{axis}: proven canonical mismatch {p} vs {a}"
    return "overlap", f"{axis}: non-critical mismatch retained as overlap {p} vs {a}"


def _relation_from_axes(
    witnesses: Sequence[AxisRelationWitness],
    *,
    candidate: GroundingCandidateAtom,
    policy: GroundingEnginePolicy,
) -> SelectedRelation:
    by_axis = {item.axis: item.relation for item in witnesses}
    critical_relations = [by_axis[axis] for axis in CRITICAL_AXES if axis in by_axis]
    critical_contradiction = any(item == "contradiction" for item in critical_relations)
    unresolved_critical = any(item == "unknown" for item in critical_relations)
    if policy.allow_surface_similarity_exact and candidate.retrieval_score >= 0.8:
        return "exact"
    if policy.over_veto_unproven and unresolved_critical and candidate.retrieved_as_neighbor:
        return "false-analog"
    if critical_contradiction and not policy.disable_critical_veto:
        return "false-analog" if candidate.retrieved_as_neighbor else "partial"
    if unresolved_critical:
        return "unknown"
    if all(item == "equivalent" for item in critical_relations):
        noncritical = [item.relation for item in witnesses if item.axis not in CRITICAL_AXES]
        if all(item in {"equivalent", "unknown"} for item in noncritical):
            return "exact"
        if any(item == "narrower" for item in noncritical):
            return "certified-specialization"
        if any(item == "broader" for item in noncritical):
            return "generalization"
        return "partial"
    if all(item in {"equivalent", "narrower"} for item in critical_relations):
        return "certified-specialization"
    if all(item in {"equivalent", "broader"} for item in critical_relations):
        return "generalization"
    return "partial"


def _proposal_verdict(
    results: Sequence[CandidateRelationResult],
    *,
    candidates: Sequence[GroundingCandidateAtom],
    parsed: ParsedProposal,
    reference: CredalReference,
    retrieval_indexed_edge_count: int,
    policy: GroundingEnginePolicy,
) -> _ProposalVerdict:
    coverage_claim = _known_space_coverage_claim(
        parsed,
        candidates=candidates,
        reference=reference,
        retrieval_indexed_edge_count=retrieval_indexed_edge_count,
    )
    if not results:
        return _ProposalVerdict(
            selected_relation="unknown",
            representative=None,
            coverage_claim=coverage_claim,
        )
    candidate_by_id = {candidate.atom_id: candidate for candidate in candidates}
    sat_results = [result for result in results if result.solver_status == "SAT"]
    if not sat_results:
        blocked = [result for result in results if result.solver_status == "UNSAT"]
        representative = _rank_candidate_results(blocked, candidate_by_id)[0] if blocked else None
        return _ProposalVerdict(
            selected_relation="blocked" if representative is not None else "unknown",
            representative=representative,
            coverage_claim=coverage_claim,
        )

    safe_cover_relations = {"exact", "certified-specialization", "compositional"}
    safe_covers = [
        result
        for result in sat_results
        if result.selected_relation in safe_cover_relations
        and not candidate_by_id.get(
            result.atom_id,
            _EMPTY_COUNTER_SENTINEL,
        ).is_adversarial_countercandidate
    ]
    if safe_covers:
        representative = _rank_candidate_results(safe_covers, candidate_by_id)[0]
        return _ProposalVerdict(
            selected_relation=representative.selected_relation,
            representative=representative,
            coverage_claim=coverage_claim,
        )

    false_analogs = [
        result for result in sat_results if result.selected_relation == "false-analog"
    ]
    coverage_sufficient = bool(coverage_claim.get("coverage_sufficient"))
    proposal_has_denotation = bool(
        coverage_claim.get("proposal_registered_ops")
        or coverage_claim.get("proposal_registered_targets")
    )
    if (
        false_analogs
        and coverage_sufficient
        and proposal_has_denotation
        and not policy.disable_novel_candidate_verdict
    ):
        representative = _rank_candidate_results(false_analogs, candidate_by_id)[0]
        coverage_claim["proposal_verdict_basis"] = (
            "no_known_atom_safely_covers; nearest_retrieved_atoms_are_false_analogs"
        )
        return _ProposalVerdict(
            selected_relation="novel-candidate",
            representative=representative,
            coverage_claim=coverage_claim,
        )

    representative = _rank_candidate_results(sat_results, candidate_by_id)[0]
    selected_relation: SelectedRelation = "unknown"
    coverage_claim["proposal_verdict_basis"] = "coverage_insufficient_or_abstained"
    return _ProposalVerdict(
        selected_relation=selected_relation,
        representative=representative,
        coverage_claim=coverage_claim,
    )


def _rank_candidate_results(
    results: Sequence[CandidateRelationResult],
    candidate_by_id: Mapping[str, GroundingCandidateAtom],
) -> list[CandidateRelationResult]:
    relation_rank = {
        "exact": 0,
        "certified-specialization": 1,
        "compositional": 2,
        "generalization": 3,
        "partial": 4,
        "false-analog": 5,
        "unknown": 6,
        "blocked": 7,
        "novel-candidate": 8,
    }
    return sorted(
        results,
        key=lambda item: (
            relation_rank.get(item.selected_relation, 99),
            candidate_by_id.get(
                item.atom_id,
                _EMPTY_COUNTER_SENTINEL,
            ).is_adversarial_countercandidate,
            -item.retrieval_score,
            grounding_candidate_semantic_sort_key(
                candidate_by_id.get(item.atom_id, _EMPTY_COUNTER_SENTINEL)
            ),
            item.hypothesis_id,
        ),
    )


_EMPTY_COUNTER_SENTINEL = GroundingCandidateAtom(
    atom_id="cg1_missing_candidate_sentinel",
    signature=MechanisticSignature(),
)


def grounding_candidate_semantic_sort_key(
    candidate: GroundingCandidateAtom,
) -> str:
    """Return a canonical candidate key that excludes owner content identities.

    Atom ids, WMR versions, evidence refs, reference lifts, and retrieval
    provenance are content-addressed owner identities.  They may change when an
    otherwise identical reference is reissued, so none may decide which
    semantic witness represents an equal-score relation.  The remaining
    relation-axis fields are the causal denotation used solely as a
    deterministic tie-break.
    """

    signature = candidate.signature
    relation_axes = {
        axis: _axis_value(signature, axis)
        for axis in RELATION_AXES
        if axis != "wm_version"
    }
    return json.dumps(
        _json_ready(relation_axes),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _known_space_coverage_claim(
    parsed: ParsedProposal,
    *,
    candidates: Sequence[GroundingCandidateAtom],
    reference: CredalReference,
    retrieval_indexed_edge_count: int,
) -> dict[str, Any]:
    registered_ops = {
        _canonical_operator(edge.edge_id)
        for edge in reference.essential_edges.values()
        if edge.modality == "L6_KNOB_OPERATOR"
    }
    writable_slots = set(_writable_wmr_slots(reference))
    proposal_ops = {
        _canonical_operator(hypothesis.signature.op)
        for hypothesis in parsed.hypotheses
        if hypothesis.signature.op
    }
    proposal_targets = {
        _canonical_variable(target)
        for hypothesis in parsed.hypotheses
        for target in hypothesis.signature.X_do
        if target
    }
    out_of_lever_ops = sorted(op for op in proposal_ops if op not in registered_ops)
    out_of_lever_targets = sorted(
        target for target in proposal_targets if target not in writable_slots
    )
    base_candidates = [
        candidate for candidate in candidates if not candidate.is_adversarial_countercandidate
    ]
    counter_reasons = sorted(
        {
            str(candidate.countercandidate_reason)
            for candidate in candidates
            if candidate.is_adversarial_countercandidate and candidate.countercandidate_reason
        }
    )
    coverage_sufficient = (
        len(reference.essential_edges) > 0
        and retrieval_indexed_edge_count == len(reference.essential_edges)
        and bool(base_candidates)
    )
    return {
        "coverage_sufficient": coverage_sufficient,
        "reference_edge_count": len(reference.essential_edges),
        "retrieval_indexed_edge_count": retrieval_indexed_edge_count,
        "registered_operator_count": len(registered_ops),
        "writable_wmr_slot_count": len(writable_slots),
        "atom_universe_count": len(_reference_atoms_from_cg0(reference)),
        "base_candidate_count": len(base_candidates),
        "adversarial_countercandidate_count": len(candidates) - len(base_candidates),
        "adversarial_countercandidate_reasons": counter_reasons,
        "proposal_registered_ops": sorted(proposal_ops),
        "proposal_registered_targets": sorted(proposal_targets),
        "out_of_lever_ops": out_of_lever_ops,
        "out_of_lever_targets": out_of_lever_targets,
        "known_space_verdict": (
            "out_of_lever" if out_of_lever_ops or out_of_lever_targets else "in_lever_space"
        ),
    }


def _recommended_transition(
    relation: SelectedRelation,
    *,
    allow_bind_recommendations: bool,
) -> RecommendedTransition:
    if allow_bind_recommendations and relation in {"exact", "certified-specialization"}:
        return "exact_bind"  # type: ignore[return-value]
    if relation == "false-analog" or relation == "blocked":
        return "quarantine"
    if relation == "compositional":
        return "bundle_bind-suggestion"
    if relation == "novel-candidate":
        return "handoff_RT3"
    return "shadow"


def _adversarial_countercandidates(
    candidates: Sequence[GroundingCandidateAtom],
    parsed: ParsedProposal,
) -> tuple[GroundingCandidateAtom, ...]:
    counters: list[GroundingCandidateAtom] = []
    proposal_targets = {
        target for hypothesis in parsed.hypotheses for target in hypothesis.signature.X_do
    }
    for candidate in candidates[:4]:
        signature = candidate.signature
        replacement_target = _counter_target(signature.X_do, proposal_targets)
        if replacement_target:
            counters.append(
                _mutated_countercandidate(
                    candidate,
                    updates={
                        "X_do": (replacement_target,),
                        "effect_path": (signature.op or _UNKNOWN, replacement_target),
                        "population": _population_for_slot(replacement_target),
                        "scope": _scope_for_slot(replacement_target),
                    },
                    reason="adversarial_false_analog_target_swap",
                )
            )
        replacement_op = _counter_operator(signature.op)
        if replacement_op:
            counters.append(
                _mutated_countercandidate(
                    candidate,
                    updates={
                        "op": replacement_op,
                        "effect_path": (replacement_op, *signature.X_do, *signature.outcome),
                    },
                    reason="adversarial_false_analog_op_swap",
                )
            )
        if signature.sign:
            counters.append(
                _mutated_countercandidate(
                    candidate,
                    updates={"sign": _opposite_sign(signature.sign)},
                    reason="adversarial_false_analog_sign_swap",
                )
            )
        if signature.params or signature.x_do:
            counters.append(
                _mutated_countercandidate(
                    candidate,
                    updates={
                        "x_do": _counter_params(signature.x_do or signature.params),
                        "params": _counter_params(signature.params or signature.x_do),
                        "unit": _counter_unit(signature.unit),
                    },
                    reason="adversarial_false_analog_do_value_unit_swap",
                )
            )
        replacement_scope, replacement_population = _counter_scope_population(
            signature.scope,
            signature.population,
        )
        counters.append(
            _mutated_countercandidate(
                candidate,
                updates={
                    "scope": replacement_scope,
                    "population": replacement_population,
                },
                reason="adversarial_false_analog_scope_population_swap",
            )
        )
        if signature.estimand:
            counters.append(
                _mutated_countercandidate(
                    candidate,
                    updates={"estimand": "controlled_direct_effect"},
                    reason="adversarial_false_analog_estimand_swap",
                )
            )
        replacement_outcome = _counter_outcome(signature.outcome, signature.X_do)
        if replacement_outcome:
            counters.append(
                _mutated_countercandidate(
                    candidate,
                    updates={
                        "outcome": (replacement_outcome,),
                        "effect_path": (
                            signature.op or _UNKNOWN,
                            *signature.X_do,
                            replacement_outcome,
                        ),
                    },
                    reason="adversarial_false_analog_proxy_outcome_swap",
                )
            )
    unique: dict[str, GroundingCandidateAtom] = {}
    for counter in counters:
        unique[counter.atom_id] = counter
    return tuple(
        sorted(
            unique.values(),
            key=grounding_candidate_semantic_sort_key,
        )
    )


def _mutated_countercandidate(
    candidate: GroundingCandidateAtom,
    *,
    updates: Mapping[str, Any],
    reason: str,
) -> GroundingCandidateAtom:
    signature = candidate.signature.model_copy(update=dict(updates))
    atom_hash = gy_content_hash(
        {
            "base_atom_id": candidate.atom_id,
            "reason": reason,
            "signature": signature.model_dump(mode="json"),
        }
    )
    return GroundingCandidateAtom(
        atom_id=f"cg1_counter_{atom_hash.removeprefix('sha256:')[:16]}",
        signature=signature,
        edge_scope=candidate.edge_scope,
        reference_lift=candidate.reference_lift,
        retrieved_as_neighbor=True,
        retrieval_reasons=(
            *candidate.retrieval_reasons,
            "adversarial_false_analog_countercandidate",
            reason,
        ),
        retrieval_score=max(candidate.retrieval_score, 0.5),
        is_adversarial_countercandidate=True,
        countercandidate_reason=reason,
    )


def _relation_set_payload(
    results: Sequence[CandidateRelationResult],
    *,
    candidates: Sequence[GroundingCandidateAtom],
    coverage_claim: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "axis_universe": list(RELATION_AXES),
        "critical_axis_universe": list(CRITICAL_AXES),
        "relation_universe": list(RELATION_UNIVERSE),
        "proposal_level_verdict_rule": (
            "safe_cover_exact_specialization_compositional_else_novel_candidate_when_"
            "full_known_space_covered_and_retrieved_neighbors_are_rejected_or_false_analog"
        ),
        "known_space_coverage": dict(coverage_claim),
        "candidate_atom_count": len(candidates),
        "base_candidate_atom_count": sum(
            1 for candidate in candidates if not candidate.is_adversarial_countercandidate
        ),
        "adversarial_countercandidate_count": sum(
            1 for candidate in candidates if candidate.is_adversarial_countercandidate
        ),
        "candidate_results": [
            result.model_dump(mode="json")
            for result in sorted(
                results,
                key=lambda item: (item.hypothesis_id, item.atom_id),
            )
        ],
    }


def _proposal_signature_payload(parsed: ParsedProposal) -> dict[str, Any]:
    return {
        "canonical_ast": parsed.canonical_ast,
        "hypotheses": [hypothesis.model_dump(mode="json") for hypothesis in parsed.hypotheses],
    }


def _atom_signature_payload(candidates: Sequence[GroundingCandidateAtom]) -> dict[str, Any]:
    return {
        candidate.atom_id: {
            "edge_scope": list(candidate.edge_scope),
            "is_adversarial_countercandidate": candidate.is_adversarial_countercandidate,
            "countercandidate_reason": candidate.countercandidate_reason,
            "reference_lift": candidate.reference_lift,
            "retrieval_reasons": list(candidate.retrieval_reasons),
            "signature": candidate.signature.model_dump(mode="json"),
        }
        for candidate in sorted(candidates, key=lambda item: item.atom_id)
    }


def _cross_modal_payload(
    results: Sequence[CandidateRelationResult],
    selected: CandidateRelationResult | None,
    *,
    gy_k_witness_mode: str,
) -> dict[str, Any]:
    payload = {
        "solver": "ortools_cp_sat",
        "numeric_scaling": NUMERIC_SCALING,
        "dense_embeddings": "deferred",
        "retrieval_is_prioritization_only": True,
        "gy_k_is_witness_only": True,
        "gy_k_witness_mode": gy_k_witness_mode,
    }
    if selected is not None:
        payload["selected_pair"] = {
            "atom_id": selected.atom_id,
            "hypothesis_id": selected.hypothesis_id,
            "solver_status": selected.solver_status,
            "unsat_core_if_any": list(selected.unsat_core_if_any),
        }
    payload["pair_count"] = len(results)
    return payload


def _modal_claim_payload(
    claims: Sequence[Mapping[str, str]],
    modality: str,
) -> list[dict[str, str]]:
    return [dict(claim) for claim in claims if str(claim.get("modality")) == modality]


def _residual_constraints(
    axis_witnesses: Sequence[AxisRelationWitness],
    relation: SelectedRelation,
) -> list[str]:
    if relation != "certified-specialization":
        return []
    return [
        f"{item.axis}:{item.relation}:{item.witness}"
        for item in axis_witnesses
        if item.relation == "narrower"
    ]


def _stale_conditions() -> tuple[str, ...]:
    return (
        "reference_epoch_changed",
        "reference_hash_changed",
        "scoped_edge_hash_changed",
        "L2 alignment or causal-edge repair",
        "L3 threshold/amendment/reference temporal change",
        "L6 knob/lex-map/observation-route owner validation change",
        "WorldModelRecord policy-slot map/content hash change",
    )


def _axis_value(signature: MechanisticSignature, axis: str) -> object:
    if axis == "target":
        return signature.X_do
    if axis == "do_value":
        return signature.x_do
    return getattr(signature, axis)


def _axis_confidence(relation: AxisRelation) -> float:
    if relation in {"equivalent", "contradiction", "narrower", "broader"}:
        return 1.0
    if relation == "overlap":
        return 0.72
    return 0.0


def _axis_evidence_ref(candidate: GroundingCandidateAtom, axis: str) -> str:
    if candidate.edge_scope:
        return candidate.edge_scope[0]
    return f"axis:{axis}:proposal_only"


def _signature_text_terms(signature: MechanisticSignature) -> tuple[str, ...]:
    return tuple(
        item
        for item in (
            signature.op,
            *signature.X_do,
            signature.sign,
            signature.scope,
            signature.population,
            *signature.outcome,
            *signature.effect_path,
            signature.estimand,
            signature.unit,
            json.dumps(signature.params, sort_keys=True, default=str),
        )
        if item
    )


def _edge_search_text(edge: CredalReferenceEdge) -> str:
    return " ".join(
        (
            edge.modality,
            edge.edge_id,
            edge.status,
            edge.unit or "",
            json.dumps(
                [completion.to_payload() for completion in edge.admissible_completions],
                sort_keys=True,
                default=str,
            ),
            json.dumps(edge.provenance, sort_keys=True, default=str),
        )
    )


def _edge_key_text(key: EdgeKey | tuple[str, str]) -> str:
    return f"{key[0]}::{key[1]}"


def _edge_key_from_text(value: str) -> EdgeKey:
    modality, _, edge_id = value.partition("::")
    return (modality, edge_id)


def _first_completion_value(edge: CredalReferenceEdge) -> Mapping[str, Any]:
    for completion in edge.admissible_completions:
        if isinstance(completion.value, Mapping):
            return completion.value
    return {}


def _writable_wmr_slots(reference: CredalReference) -> tuple[str, ...]:
    slots: set[str] = set()
    for edge in reference.essential_edges.values():
        if edge.modality != "WMR_POLICY_SLOT_MAP":
            continue
        value = _first_completion_value(edge)
        slot = _text(value.get("world_slot"))
        if not slot and ":" in edge.edge_id:
            slot = edge.edge_id.rsplit(":", 1)[-1]
        if slot and _slot_exists(reference, slot):
            slots.add(slot)
    if not slots:
        slots = {
            edge.edge_id
            for edge in reference.essential_edges.values()
            if edge.modality == "WMR_WORLD_SLOT"
        }
    return tuple(sorted(slots))


def _operator_target_compatible(
    reference: CredalReference,
    *,
    op_id: str,
    domain: Mapping[str, Any],
    target_slot: str,
    explicit_slots: Sequence[str],
) -> bool:
    if target_slot in explicit_slots:
        return True
    op_unit = _unit_alias(_text(domain.get("unit")))
    target_unit = _unit_alias(_unit_for_target(reference, target_slot) or "")
    if op_unit and target_unit and op_unit == target_unit:
        return True
    op = _canonical_operator(op_id)
    target = _canonical_variable(target_slot)
    if op == "tax_relief_rate":
        return "tax" in target or target_unit == "ratio"
    if op == "procurement_shock_intensity":
        return target.startswith("cells.") and any(
            token in target for token in ("distress", "output", "capacity")
        )
    if op == "budget_allocation_multiplier":
        return target in {"government.balance"} or target_unit == "usd"
    return False


def _wmr_edges_for_target(reference: CredalReference, target: str) -> list[CredalReferenceEdge]:
    return [
        edge
        for edge in reference.essential_edges.values()
        if (edge.modality == "WMR_WORLD_SLOT" and edge.edge_id == target)
        or (edge.modality == "WMR_POLICY_SLOT_MAP" and edge.edge_id.endswith(f":{target}"))
    ]


def _unit_for_target(reference: CredalReference | None, target: str) -> str | None:
    if reference is None or not target:
        return None
    edge = reference.essential_edges.get(("WMR_WORLD_SLOT", target))
    return edge.unit if edge is not None else None


def _slot_exists(reference: CredalReference, target: str) -> bool:
    return reference.essential_edges.get(("WMR_WORLD_SLOT", target)) is not None


def _knob_exists(reference: CredalReference, op: str) -> bool:
    return reference.essential_edges.get(("L6_KNOB_OPERATOR", _canonical_operator(op))) is not None


def _knob_maps_to(reference: CredalReference, op: str, target: str) -> bool:
    edge = reference.essential_edges.get(("L6_KNOB_WORLD_SLOT", _canonical_operator(op)))
    if edge is None:
        return False
    value = _first_completion_value(edge)
    return target in _string_list(value.get("target_world_slots"))


def _knob_target(reference: CredalReference, op: str) -> str:
    edge = reference.essential_edges.get(("L6_KNOB_WORLD_SLOT", _canonical_operator(op)))
    if edge is None:
        return ""
    value = _first_completion_value(edge)
    targets = _string_list(value.get("target_world_slots"))
    return targets[0] if targets else ""


def _law_token_operator_targets(
    reference: CredalReference, law_token: str
) -> list[tuple[str, str]]:
    edge = reference.essential_edges.get(("L6_LEX_INTERVENTION_MAP", law_token))
    if edge is None:
        return []
    pairs: list[tuple[str, str]] = []
    for completion in edge.admissible_completions:
        knob = _text(completion.value.get("knob_id"))
        if knob:
            pairs.append((_canonical_operator(knob), _knob_target(reference, knob)))
    return pairs


def _params_in_operator_schema(
    reference: CredalReference,
    op: str,
    params: Mapping[str, Any],
) -> bool:
    edge = reference.essential_edges.get(("L6_KNOB_OPERATOR", _canonical_operator(op)))
    if edge is None:
        return False
    domain = _mapping(_first_completion_value(edge).get("parameter_domain"))
    minimum = _float(domain.get("min_value"))
    maximum = _float(domain.get("max_value"))
    numeric_values = [_float(value) for value in params.values()]
    numeric_values = [value for value in numeric_values if value is not None]
    if not numeric_values:
        return True
    for value in numeric_values:
        if minimum is not None and value < minimum:
            return False
        if maximum is not None and value > maximum:
            return False
    return True


def _unit_compatible(reference: CredalReference, target: str, unit: str | None) -> bool:
    if not unit:
        return True
    target_unit = _unit_for_target(reference, target)
    if not target_unit:
        return True
    return _unit_alias(unit) == _unit_alias(target_unit)


def _soft_score_basis_points(signature: MechanisticSignature) -> int:
    score = 0.2
    if signature.op:
        score += 0.2
    if signature.X_do:
        score += 0.2
    if signature.outcome:
        score += 0.1
    if signature.estimand:
        score += 0.1
    return round(min(score, 1.0) * 10_000)


def _canonical_axis_value(axis: str, value: object) -> str:
    if value is None:
        return _UNKNOWN
    if axis == "op":
        return _canonical_operator(_text(value)) or _UNKNOWN
    if axis == "sign":
        return _canonical_sign(_text(value)) or _UNKNOWN
    if axis == "estimand":
        return _canonical_estimand(_text(value)) or _UNKNOWN
    if axis in {"target", "outcome", "effect_path"}:
        values = tuple(_canonical_path_component(item) for item in _string_list(value))
        values = tuple(item for item in values if item)
        return "|".join(values) if values else _UNKNOWN
    if axis in {"do_value", "params"}:
        if not _mapping(value):
            return _UNKNOWN
        return json.dumps(_json_ready(value), sort_keys=True, default=str)
    if axis == "unit":
        return _unit_alias(_text(value)) or _UNKNOWN
    text = _text(value)
    return text.casefold() if text else _UNKNOWN


def _exact_axis_value(axis: str, value: object) -> str:
    if value is None:
        return _UNKNOWN
    if axis in {"effect_path", "target", "outcome"}:
        values = tuple(
            _text(item).casefold().replace("-", "_").replace(" ", "_")
            for item in _string_list(value)
            if _text(item)
        )
        return "|".join(values) if values else _UNKNOWN
    text = _text(value).casefold().replace("-", "_").replace(" ", "_")
    return text or _UNKNOWN


def _canonical_variable(value: object) -> str:
    text = _text(value).casefold().replace(" ", "_")
    aliases = {
        "employment_retention": "cells.employment",
        "employment_retention_rate": "cells.employment",
        "jobs": "cells.employment",
        "employment": "cells.employment",
        "production_capacity": "cells.output",
        "output": "cells.output",
        "fiscal_exposure": "government.balance",
        "government_balance": "government.balance",
        "budget_balance": "government.balance",
        "tax_rate": "global.tax_rate",
        "payroll_tax": "global.tax_rate",
        "household_income": "household_cells.disposable_income",
        "disposable_income": "household_cells.disposable_income",
        "household_transfer": "household_cells.transfer_intensity",
        "firm_distress": "cells.distress_score",
        "procurement_distress": "cells.distress_score",
    }
    return aliases.get(text, text)


def _canonical_path_component(value: object) -> str:
    """Canonicalize an effect-path component without assuming its role."""

    text = _text(value)
    op = _canonical_operator(text)
    variable = _canonical_variable(text)
    if op != text.casefold().replace("-", "_").replace(" ", "_"):
        return op
    return variable


def _canonical_operator(value: object) -> str:
    text = _text(value).casefold().replace("-", "_").replace(" ", "_")
    if not text:
        return ""
    aliases = {
        "budget": "budget_allocation_multiplier",
        "budget_allocation": "budget_allocation_multiplier",
        "budget_multiplier": "budget_allocation_multiplier",
        "tax_subsidy": "income_tax",
        "tax_credit": "tax_relief_rate",
        "tax_credit_rate": "tax_relief_rate",
        "income_tax_credit": "tax_relief_rate",
        "corporate_tax_credit": "tax_relief_rate",
        "payroll_tax_credit": "tax_relief_rate",
        "tax_relief": "tax_relief_rate",
        "procurement": "procurement_shock_intensity",
        "procurement_shock": "procurement_shock_intensity",
    }
    return aliases.get(text, text)


def _canonical_sign(value: object) -> str:
    text = _text(value).casefold().replace(" ", "_")
    if text in {"increase", "increases", "raise", "raises", "positive", "+", "higher"}:
        return "increase"
    if text in {"decrease", "decreases", "lower", "lowers", "negative", "-", "reduce", "reduces"}:
        return "decrease"
    if text in {"cap", "capped", "ceiling"}:
        return "cap"
    return text


def _canonical_estimand(value: object) -> str:
    text = _text(value).casefold().replace(" ", "_")
    aliases = {
        "ate": "average_treatment_effect",
        "average_treatment_effect": "average_treatment_effect",
        "total_effect": "total_effect",
        "late": "local_average_treatment_effect",
        "local_average_treatment_effect": "local_average_treatment_effect",
        "controlled_direct": "controlled_direct_effect",
        "controlled_direct_effect": "controlled_direct_effect",
    }
    return aliases.get(text, text)


def _operator_from_text(lower: str) -> str:
    if "budget" in lower:
        return "budget_allocation_multiplier"
    if "procurement" in lower or "distress" in lower:
        return "procurement_shock_intensity"
    if "tax" in lower or "credit" in lower or "relief" in lower:
        return "tax_relief_rate"
    if "labor" in lower or "employment" in lower or "wage" in lower:
        return "labor_market"
    if "household" in lower and ("transfer" in lower or "subsidy" in lower):
        return "household_transfer"
    return ""


def _target_from_text(lower: str) -> str:
    if "global.tax_rate" in lower or "tax rate" in lower or "payroll tax" in lower:
        return "global.tax_rate"
    if (
        "government.balance" in lower
        or "government balance" in lower
        or "fiscal" in lower
        or "budget" in lower
    ):
        return "government.balance"
    if "procurement" in lower or "distress" in lower:
        return "cells.distress_score"
    if "household" in lower and ("income" in lower or "disposable" in lower):
        return "household_cells.disposable_income"
    if "household" in lower and ("transfer" in lower or "subsidy" in lower):
        return "household_cells.transfer_intensity"
    if "employment" in lower or "jobs" in lower:
        return "cells.employment"
    if "output" in lower or "production" in lower:
        return "cells.output"
    return ""


def _outcome_from_text(lower: str, target: str) -> str:
    if "employment" in lower or "jobs" in lower:
        return "cells.employment"
    if "production" in lower or "output" in lower:
        return "cells.output"
    if "fiscal" in lower or "budget" in lower or "balance" in lower:
        return "government.balance"
    if "income" in lower:
        return "household_cells.disposable_income"
    return target


def _estimand_from_text(lower: str) -> str:
    if " late" in f" {lower}" or "local average" in lower:
        return "local_average_treatment_effect"
    if "controlled direct" in lower or "direct effect" in lower:
        return "controlled_direct_effect"
    return "average_treatment_effect"


def _params_from_text(lower: str) -> dict[str, Any]:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:%|percent)", lower)
    if match:
        return {"rate": round(float(match.group(1)) / 100.0, 6)}
    decimal = re.search(r"\b0\.[0-9]+\b", lower)
    if decimal:
        return {"rate": float(decimal.group(0))}
    return {}


def _sign_from_text(lower: str) -> str:
    if any(token in lower for token in ("lower", "reduce", "decrease", "cut")):
        return "decrease"
    if any(token in lower for token in ("raise", "increase", "expand")):
        return "increase"
    if "cap" in lower:
        return "cap"
    return ""


def _law_token_from_text(lower: str) -> str:
    if "budget_law" in lower or "household threshold" in lower or "budget law" in lower:
        return "budget_law"
    if "procurement_decree" in lower or "procurement decree" in lower:
        return "procurement_decree"
    if "tax_relief_statute" in lower or "payroll tax" in lower or "tax statute" in lower:
        return "tax_relief_statute"
    return ""


def _knob_from_text(lower: str) -> str:
    if "budget_allocation_multiplier" in lower:
        return "budget_allocation_multiplier"
    if "procurement_shock_intensity" in lower:
        return "procurement_shock_intensity"
    if "tax_relief_rate" in lower or "tax_credit_rate" in lower:
        return "tax_relief_rate"
    return ""


def _method_target_from_text(lower: str) -> str:
    if "method firm" in lower or "firm late" in lower:
        return "firms.labor_count"
    if "method household" in lower:
        return "household_cells.disposable_income"
    if "method tax" in lower:
        return "global.tax_rate"
    return ""


def _method_operator_from_text(lower: str) -> str:
    if "method firm late" in lower:
        return "labor_market"
    if "method firm tax" in lower:
        return "tax_relief_rate"
    return ""


def _method_outcome_from_text(lower: str) -> str:
    if "firm late" in lower:
        return "firms.labor_count"
    return ""


def _method_estimand_from_text(lower: str) -> str:
    if "late" in lower:
        return "local_average_treatment_effect"
    return ""


def _do_target_from_text(lower: str) -> str:
    match = re.search(r"do\.target\s*=\s*([a-zA-Z0-9_.-]+)", lower)
    return match.group(1) if match else ""


def _scope_from_text(lower: str) -> str:
    if "large employer" in lower or "large firm" in lower:
        return "large_employers"
    if "industrial" in lower or "firm" in lower:
        return "firms"
    if "household" in lower:
        return "households"
    if "universal" in lower or "all " in lower:
        return "all"
    return ""


def _population_from_text(lower: str) -> str:
    if "household" in lower:
        return "households"
    if "firm" in lower or "employer" in lower or "industrial" in lower:
        return "firms"
    if "worker" in lower or "labor" in lower:
        return "workers"
    return ""


def _unit_from_text(lower: str) -> str:
    if "basis point" in lower or "bp" in lower:
        return "basis_points"
    if "%" in lower or "percent" in lower or "ratio" in lower:
        return "ratio"
    if "usd" in lower or "dollar" in lower:
        return "usd"
    return ""


def _scope_for_slot(slot: str) -> str:
    if slot.startswith("firms."):
        return "firms"
    if slot.startswith("agents."):
        return "workers"
    if slot.startswith("household_cells."):
        return "households"
    if slot.startswith("cells."):
        return "regional_cells"
    return "global"


def _population_for_slot(slot: str) -> str:
    if slot.startswith("firms."):
        return "firms"
    if slot.startswith("agents."):
        return "workers"
    if slot.startswith("household_cells."):
        return "households"
    if slot.startswith("cells."):
        return "cells"
    return "all"


def _default_outcome_for_target(target: str) -> tuple[str, ...]:
    if target == "global.tax_rate":
        return ("government.balance",)
    if target == "government.balance":
        return ("government.balance",)
    if target == "cells.distress_score":
        return ("cells.output",)
    if target.startswith("household_cells."):
        return ("household_cells.disposable_income",)
    return (target,) if target else ()


def _default_sign_for_operator(op: str | None) -> str | None:
    if op in {"tax_relief_rate", "procurement_shock_intensity"}:
        return "decrease"
    if op == "budget_allocation_multiplier":
        return "increase"
    if op and ("subsidy" in op or "transfer" in op):
        return "increase"
    return None


def _scope_from_atom(atom: Mapping[str, Any]) -> str:
    selector = _mapping(atom.get("target_selector"))
    sector_ids = _string_list(selector.get("target_sector_ids"))
    if sector_ids:
        return ",".join(sector_ids)
    return _text(selector.get("target_population_type"))


def _schedule_text(schedule: Mapping[str, Any]) -> str | None:
    if not schedule:
        return None
    return json.dumps(schedule, sort_keys=True, default=str)


def _sign_from_params(params: Mapping[str, Any]) -> str:
    for value in params.values():
        number = _float(value)
        if number is None:
            continue
        if number < 0:
            return "decrease"
        if number > 0:
            return "increase"
    return ""


def _opposite_signs(left: str, right: str) -> bool:
    return {left, right} in ({"increase", "decrease"}, {"increase", "cap"}, {"decrease", "cap"})


def _opposite_sign(sign: str) -> str:
    canonical = _canonical_sign(sign)
    if canonical == "increase":
        return "decrease"
    if canonical == "decrease":
        return "increase"
    return "increase"


def _narrower_scope(left: str, right: str) -> bool:
    pairs = {
        ("large_employers", "firms"),
        ("firms", "all"),
        ("workers", "all"),
        ("households", "all"),
        ("regional_cells", "all"),
    }
    return (left, right) in pairs


def _param_subset(left: object, right: object) -> bool:
    left_map = _mapping(left)
    right_map = _mapping(right)
    domain = _mapping(right_map.get("domain"))
    if not domain:
        return False
    minimum = _float(domain.get("min_value"))
    maximum = _float(domain.get("max_value"))
    for value in left_map.values():
        numeric = _float(value)
        if numeric is None:
            continue
        if minimum is not None and numeric < minimum:
            return False
        return not (maximum is not None and numeric > maximum)
    return False


def _concrete_params_conflict(left: object, right: object) -> bool:
    left_map = _mapping(left)
    right_map = _mapping(right)
    if not left_map or not right_map:
        return False
    if _mapping(left_map.get("domain")) or _mapping(right_map.get("domain")):
        return False
    shared = set(left_map).intersection(right_map)
    if not shared:
        return False
    for key in shared:
        left_number = _float(left_map.get(key))
        right_number = _float(right_map.get(key))
        if left_number is not None and right_number is not None:
            if round(left_number, 9) != round(right_number, 9):
                return True
        elif _text(left_map.get(key)) != _text(right_map.get(key)):
            return True
    return False


def _params_overlap(left: object, right: object) -> bool:
    return bool(_mapping(left)) and bool(_mapping(right))


def _unit_alias(value: str) -> str:
    text = _text(value).casefold()
    aliases = {
        "%": "ratio",
        "percent": "ratio",
        "percentage": "ratio",
        "basis_points": "ratio",
        "bp": "ratio",
        "usd": "usd",
        "dollar": "usd",
        "dollars": "usd",
    }
    return aliases.get(text, text)


def _counter_target(
    current_targets: Sequence[str],
    proposal_targets: set[str],
) -> str:
    for target in (
        "household_cells.disposable_income",
        "global.tax_rate",
        "government.balance",
        "cells.distress_score",
    ):
        if target not in current_targets and target not in proposal_targets:
            return target
    return ""


def _counter_operator(current_op: str | None) -> str:
    current = _canonical_operator(current_op)
    for op in (
        "budget_allocation_multiplier",
        "tax_relief_rate",
        "procurement_shock_intensity",
        "labor_market",
        "household_transfer",
    ):
        if op != current:
            return op
    return ""


def _counter_params(value: object) -> dict[str, Any]:
    params = dict(_mapping(value))
    if not params:
        return {"rate": -0.01}
    domain = _mapping(params.get("domain"))
    if domain:
        minimum = _float(domain.get("min_value"))
        maximum = _float(domain.get("max_value"))
        if minimum is not None:
            return {"rate": round(minimum - 0.01, 6)}
        if maximum is not None:
            return {"rate": round(maximum + 0.01, 6)}
        return {"rate": -0.01}
    counter: dict[str, Any] = {}
    for key, raw in params.items():
        number = _float(raw)
        if number is None:
            counter[str(key)] = f"not_{raw}"
        elif number == 0:
            counter[str(key)] = -0.01
        else:
            counter[str(key)] = round(-number, 6)
    return counter


def _counter_unit(unit: str | None) -> str:
    canonical = _unit_alias(unit or "")
    if canonical == "ratio":
        return "usd"
    return "ratio"


def _counter_scope_population(scope: str | None, population: str | None) -> tuple[str, str]:
    current_scope = _text(scope)
    current_population = _text(population)
    for candidate_scope, candidate_population in (
        ("households", "households"),
        ("firms", "firms"),
        ("workers", "workers"),
        ("regional_cells", "cells"),
        ("global", "all"),
    ):
        if candidate_scope != current_scope or candidate_population != current_population:
            return candidate_scope, candidate_population
    return "households", "households"


def _counter_outcome(
    current_outcomes: Sequence[str],
    current_targets: Sequence[str],
) -> str:
    current = {
        _canonical_variable(item) for item in (*current_outcomes, *current_targets) if item
    }
    for outcome in (
        "household_cells.disposable_income",
        "government.balance",
        "cells.output",
        "cells.distress_score",
        "firms.labor_count",
    ):
        if outcome not in current:
            return outcome
    return ""


def _has_l2_alignment_hint(parsed: ParsedProposal, atom: GroundingCandidateAtom) -> bool:
    proposal_tokens = _tokens(parsed.raw_text)
    atom_aliases = _operator_surface_aliases(atom.signature.op)
    if proposal_tokens & atom_aliases:
        return True
    if {"synonym", "alias"} & proposal_tokens:
        atom_terms = _tokens(" ".join(_signature_text_terms(atom.signature)))
        return bool(proposal_tokens & atom_terms)
    return False


def _operator_surface_aliases(op: str | None) -> set[str]:
    canonical = _canonical_operator(op)
    aliases = {
        "tax_relief_rate": {"tax", "credit", "relief", "payroll", "levy", "rate"},
        "budget_allocation_multiplier": {"budget", "allocation", "appropriation", "balance"},
        "procurement_shock_intensity": {"procurement", "distress", "shock"},
    }
    return aliases.get(canonical, {canonical} if canonical else set())


def _has_l3_or_l6_hint(parsed: ParsedProposal, atom: GroundingCandidateAtom) -> bool:
    text = parsed.raw_text.casefold()
    return bool(atom.signature.op and atom.signature.op in text) or any(
        token in text for token in ("law", "statute", "decree", "threshold", "knob")
    )


def _has_causal_neighbourhood_hint(parsed: ParsedProposal, atom: GroundingCandidateAtom) -> bool:
    proposal_terms = {
        term
        for hypothesis in parsed.hypotheses
        for term in _signature_text_terms(hypothesis.signature)
    }
    atom_terms = set(_signature_text_terms(atom.signature))
    return bool(_tokens(" ".join(proposal_terms)) & _tokens(" ".join(atom_terms)))


def _var_token(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", value)[:80] or "unknown"


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in _TOKEN_RE.findall(value) if len(token) > 1}


def _raw_text_from_mapping(payload: Mapping[str, Any]) -> str:
    for key in ("raw_text", "narrative", "summary", "description", "text", "proposal_text"):
        text = _text(payload.get(key))
        if text:
            return text
    return json.dumps(_json_ready(payload), sort_keys=True, default=str)


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        if "|" in value:
            return [item.strip() for item in value.split("|") if item.strip()]
        return [value.strip()] if value.strip() else []
    if isinstance(value, Mapping):
        return [json.dumps(_json_ready(value), sort_keys=True, default=str)]
    if isinstance(value, Sequence):
        return [_text(item) for item in value if _text(item)]
    return [_text(value)] if _text(value) else []


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_list(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    text = _text(value).replace("%", "")
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    if "%" in _text(value):
        return parsed / 100.0
    return parsed


def _json_ready(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


__all__ = [
    "CRITICAL_AXES",
    "GROUNDING_RELATION_SCHEMA_VERSION",
    "GROUNDING_RELATION_VALIDATOR_VERSION",
    "NUMERIC_SCALING",
    "RELATION_AXES",
    "RELATION_UNIVERSE",
    "AxisEntailmentWitness",
    "AxisRelationWitness",
    "GroundingCandidateAtom",
    "GroundingEnginePolicy",
    "GroundingRelationCertificate",
    "GroundingRelationEngine",
    "MechanisticSignature",
    "ParsedProposal",
    "ProposalHypothesis",
    "build_grounding_relation_certificate",
    "parse_n4_proposal",
]
