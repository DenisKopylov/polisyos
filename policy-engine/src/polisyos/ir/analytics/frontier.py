"""Phase-closure frontier artifacts, manifests, and validator helpers.

The research-result plan requires more than isolated implementations: every
stage must carry a benchmark proxy, a typed downstream target, an explicit
promotion story, and machine-checkable evidence that the repository can point
to.  This module stores the checked-in manifests for Phases 1-4, keeps the
frontier sketch contract used by scoped theorem families, and exposes a
validator that turns the checked-in manifests into a repo-tracked closure
report.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import FrontierSketchRef

if TYPE_CHECKING:
    from ..refs import ArtifactRefModel
else:
    from ..refs import ArtifactRefModel

StageClosureState = Literal["execution_grade", "narrow_accepted", "deferred_or_refuted"]
ValidationSeverity = Literal["info", "error"]
ValidationStatus = Literal["complete", "incomplete"]

_DEFAULT_PLAN_DOC_PATH = "docs/archive/plans/CAUSAL_ENGINE_RESEARCH_RESULT_PLAN.md"
_DEFAULT_CLOSURE_TEST = "tests/ir/analytics/test_phase_closure_contracts.py"
_PHASE_ID_BY_NUMBER = {
    "1": "phase_1_first_production_unlocks_and_certificate_foundations",
    "2": "phase_2_query_expansion_and_first_production_facing_upgrades",
    "3": "phase_3_dependency_driven_advanced_integration",
    "4": "phase_4_consolidation_promotion_completeness_and_long_horizon_moat",
}
_PHASE_HEADING_PATTERN = re.compile(r"^## Phase (?P<number>[1-4])\b")
_STAGE_HEADING_PATTERN = re.compile(r"^### Stage (?P<stage_id>\d+\.\d+) — (?P<title>.+)$")


def _clean_stage_token(value: object, *, field_name: str) -> str:
    candidate = str(value).strip()
    if not candidate:
        raise ValueError(f"{field_name} must be non-empty")
    return candidate


def _clean_non_empty_list(values: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{field_name} must be a tuple/list of strings")
    cleaned = tuple(_clean_stage_token(item, field_name=field_name) for item in values)
    if not cleaned:
        raise ValueError(f"{field_name} must be non-empty")
    return cleaned


def _clean_optional_non_empty_list(values: object, *, field_name: str) -> tuple[str, ...]:
    if values in (None, ()):
        return ()
    return _clean_non_empty_list(values, field_name=field_name)


def _clean_optional_string(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    if not candidate:
        raise ValueError(f"{field_name} must be non-empty when provided")
    return candidate


def _stable_unique_strings(values: list[str]) -> tuple[str, ...]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        candidate = value.strip()
        if candidate and candidate not in seen:
            seen.add(candidate)
            output.append(candidate)
    return tuple(output)


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _evidence_tests(*paths: str) -> tuple[str, ...]:
    return _stable_unique_strings([_DEFAULT_CLOSURE_TEST, *paths])


def _stage_declaration_data(
    *,
    stage_id: str,
    title: str,
    benchmark_proxy: list[str] | tuple[str, ...],
    typed_integration_target: str,
    required_for_promotion: list[str] | tuple[str, ...],
    scope_statement: str,
    evidence_tests: list[str] | tuple[str, ...],
    backbone: bool = False,
    canonical_contract_surface: str | None = None,
    closure_state: StageClosureState = "execution_grade",
    boundary_reason: str | None = None,
    downstream_promotion_rule: str | None = None,
    kill_rule: str | None = None,
    evidence_docs: list[str] | tuple[str, ...] | None = None,
    evidence_contracts: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    canonical_surface = canonical_contract_surface or typed_integration_target
    docs = tuple(evidence_docs or (_DEFAULT_PLAN_DOC_PATH,))
    contracts = tuple(evidence_contracts or (canonical_surface,))
    return {
        "stage_id": stage_id,
        "backbone": backbone,
        "title": title,
        "benchmark_proxy": list(benchmark_proxy),
        "typed_integration_target": typed_integration_target,
        "required_for_promotion": list(required_for_promotion),
        "canonical_contract_surface": canonical_surface,
        "scope_statement": scope_statement,
        "closure_state": closure_state,
        "boundary_reason": boundary_reason,
        "downstream_promotion_rule": downstream_promotion_rule,
        "kill_rule": kill_rule,
        "evidence_tests": list(evidence_tests),
        "evidence_docs": list(docs),
        "evidence_contracts": list(contracts),
    }


class PhaseStageDeclaration(BaseModel):
    """Checked-in declaration for one stage and its closure contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stage_id: str
    backbone: bool = False
    title: str
    benchmark_proxy: tuple[str, ...]
    typed_integration_target: str
    required_for_promotion: tuple[str, ...]
    canonical_contract_surface: str
    scope_statement: str
    closure_state: StageClosureState = "execution_grade"
    boundary_reason: str | None = None
    downstream_promotion_rule: str | None = None
    kill_rule: str | None = None
    evidence_tests: tuple[str, ...]
    evidence_docs: tuple[str, ...] = ()
    evidence_contracts: tuple[str, ...] = ()

    @field_validator(
        "stage_id",
        "title",
        "typed_integration_target",
        "canonical_contract_surface",
        "scope_statement",
        mode="before",
    )
    @classmethod
    def _validate_non_empty_string(cls, value: object, info: Any) -> str:
        return _clean_stage_token(value, field_name=str(info.field_name))

    @field_validator(
        "benchmark_proxy",
        "required_for_promotion",
        "evidence_tests",
        mode="before",
    )
    @classmethod
    def _validate_non_empty_items(cls, value: object, info: Any) -> tuple[str, ...]:
        return _clean_non_empty_list(value, field_name=str(info.field_name))

    @field_validator("evidence_docs", "evidence_contracts", mode="before")
    @classmethod
    def _validate_optional_items(cls, value: object, info: Any) -> tuple[str, ...]:
        return _clean_optional_non_empty_list(value, field_name=str(info.field_name))

    @field_validator("boundary_reason", "downstream_promotion_rule", "kill_rule", mode="before")
    @classmethod
    def _validate_optional_string_fields(cls, value: object, info: Any) -> str | None:
        return _clean_optional_string(value, field_name=str(info.field_name))

    @model_validator(mode="after")
    def _validate_closure_state_fields(self) -> PhaseStageDeclaration:
        if self.closure_state != "execution_grade":
            if self.boundary_reason is None:
                raise ValueError("boundary_reason is required for non-execution closure states")
            if self.downstream_promotion_rule is None:
                raise ValueError(
                    "downstream_promotion_rule is required for non-execution closure states"
                )
            if self.kill_rule is None:
                raise ValueError("kill_rule is required for non-execution closure states")
        return self


class PhaseClosureManifest(BaseModel):
    """Manifest of stage declarations required to close a research phase."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    phase_id: str
    execution_intent: str
    phase_gate: str
    stages: tuple[PhaseStageDeclaration, ...]

    @field_validator("phase_id", "execution_intent", "phase_gate", mode="before")
    @classmethod
    def _validate_manifest_strings(cls, value: object, info: Any) -> str:
        return _clean_stage_token(value, field_name=str(info.field_name))

    @field_validator("stages", mode="before")
    @classmethod
    def _validate_stages(cls, value: object) -> tuple[PhaseStageDeclaration, ...]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("stages must be a tuple/list of stage declarations")
        stages = tuple(
            item
            if isinstance(item, PhaseStageDeclaration)
            else PhaseStageDeclaration.model_validate(item)
            for item in value
        )
        if not stages:
            raise ValueError("stages must be non-empty")
        return stages

    @model_validator(mode="after")
    def _validate_unique_stage_ids(self) -> PhaseClosureManifest:
        stage_ids = [stage.stage_id for stage in self.stages]
        if len(set(stage_ids)) != len(stage_ids):
            raise ValueError("phase manifest contains duplicate stage_id values")
        return self

    def stage_map(self) -> dict[str, PhaseStageDeclaration]:
        return {stage.stage_id: stage for stage in self.stages}


class FrontierSketch(BaseModel):
    """Persisted research-boundary sketch attached to a scoped production artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    stage_id: str
    family: str
    sketch_type: str
    hypothesis: str
    benchmark_proxy: tuple[str, ...]
    typed_integration_target: str
    known_limitations: tuple[str, ...] = ()
    required_for_promotion: tuple[str, ...]
    primary_ref: ArtifactRefModel | None = None
    canonical_contract_surface: str
    max_readiness: Literal["PROOF_ONLY"] = "PROOF_ONLY"
    ttl_phases: int = Field(default=3, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "stage_id",
        "family",
        "sketch_type",
        "hypothesis",
        "typed_integration_target",
        "canonical_contract_surface",
        mode="before",
    )
    @classmethod
    def _validate_strings(cls, value: object, info: Any) -> str:
        return _clean_stage_token(value, field_name=str(info.field_name))

    @field_validator(
        "benchmark_proxy",
        "known_limitations",
        "required_for_promotion",
        mode="before",
    )
    @classmethod
    def _validate_tuple_payloads(cls, value: object, info: Any) -> tuple[str, ...]:
        return _clean_non_empty_list(value, field_name=str(info.field_name))


class DocumentStageEntry(BaseModel):
    """First-occurrence stage entry parsed from the source plan document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stage_id: str
    title: str
    phase_id: str
    source_line: int = Field(ge=1)


class PhaseClosureValidationIssue(BaseModel):
    """One machine-readable closure validation issue."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    severity: ValidationSeverity = "error"
    code: str
    message: str
    phase_id: str | None = None
    stage_id: str | None = None
    path: str | None = None


class StageClosureValidationResult(BaseModel):
    """Validation verdict for one stage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    phase_id: str
    stage_id: str
    title: str
    closure_state: StageClosureState
    status: ValidationStatus
    typed_integration_target: str
    canonical_contract_surface: str
    benchmark_proxy: tuple[str, ...]
    evidence_tests: tuple[str, ...]
    evidence_docs: tuple[str, ...]
    evidence_contracts: tuple[str, ...]
    missing_paths: tuple[str, ...] = ()
    issue_codes: tuple[str, ...] = ()


class PhaseClosureValidationReport(BaseModel):
    """Machine-readable closure report over all checked-in phase manifests."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    source_document: str
    repo_root: str
    overall_status: ValidationStatus
    phase_status: dict[str, ValidationStatus]
    stage_results: tuple[StageClosureValidationResult, ...]
    issues: tuple[PhaseClosureValidationIssue, ...] = ()
    duplicate_document_stages: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    regression: dict[str, Any] = Field(default_factory=dict)


PHASE1_CLOSURE_MANIFEST = PhaseClosureManifest.model_validate(
    {
        "phase_id": _PHASE_ID_BY_NUMBER["1"],
        "execution_intent": (
            "Create the first machine-checkable theorem/certificate contracts that directly "
            "unlock production integration and anchor later phases."
        ),
        "phase_gate": (
            "Every stage has a benchmark proxy, a typed integration target, and a concrete "
            "proof/certificate contract consumable by downstream phases."
        ),
        "stages": [
            _stage_declaration_data(
                stage_id="2.1",
                backbone=True,
                title="Identifiability preservation under latent interface variables",
                benchmark_proxy=[
                    "latent front-door positive case",
                    "hedge counterexample",
                    "unresolved latent sentinel",
                ],
                typed_integration_target="CompositionCertificate.query_certificates",
                required_for_promotion=[
                    "exact latent-projection replay",
                    "persisted negative witness",
                    "scientist consumer path",
                ],
                scope_statement=(
                    "Phase 1 closes latent-preservation certificates for supported reconciliation "
                    "paths while keeping unresolved latent structure in frontier-scoped artifacts."
                ),
                closure_state="narrow_accepted",
                boundary_reason=(
                    "Current theorem-backed coverage is limited to supported latent-projection and "
                    "hedge-detection reconciliation paths."
                ),
                downstream_promotion_rule=(
                    "Promote only certificates emitted by the canonical query-preservation path; "
                    "all unresolved latent cases must carry an explicit negative/frontier witness."
                ),
                kill_rule=(
                    "Do not claim latent-preservation completeness beyond supported reconciliation "
                    "families or unresolved-latent sentinels."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_query_preservation.py",
                    "tests/ir/analytics/test_phase1_closure_contracts.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="3.1",
                backbone=True,
                title="Sharpness proofs for complex query families",
                benchmark_proxy=[
                    "known sharp LP family",
                    "non-sharp relaxed family sentinel",
                ],
                typed_integration_target="BoundsBundle.dual_certificate_ref",
                required_for_promotion=[
                    "dual validation",
                    "CAS round-trip",
                    "sharpness_status recompute",
                ],
                scope_statement=(
                    "Phase 1 closes LP-backed dual certificates for supported exact and relaxed "
                    "bound families."
                ),
                evidence_tests=_evidence_tests(
                    "tests/ir/analytics/test_phase1_closure_contracts.py",
                    "tests/ir/analytics/test_phase_a_contracts.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="4.4",
                backbone=True,
                title="Dynamic SCM semantics and σ-separation for proof kernel",
                benchmark_proxy=[
                    "stable reducible cycle",
                    "sigma-fail sentinel",
                    "non-well-posed cycle",
                ],
                typed_integration_target="ProofBundle.dynamic_semantics",
                required_for_promotion=[
                    "validated reduction class",
                    "well-posedness witness",
                    "explicit boundary artifact for unsupported cycles",
                ],
                scope_statement=(
                    "Phase 1 certifies validated linear-unique cyclic reductions and routes "
                    "unsupported cycle families through explicit frontier artifacts."
                ),
                closure_state="narrow_accepted",
                boundary_reason=(
                    "Dynamic semantics are theorem-backed only for validated linear-unique cyclic "
                    "reductions and explicit well-posedness witnesses."
                ),
                downstream_promotion_rule=(
                    "Downstream dynamic/cyclic consumers may promote only runs with validated "
                    "dynamic semantics attachments; other cycles must remain capped by frontier "
                    "artifacts."
                ),
                kill_rule=(
                    "Do not claim general cyclic σ-separation support beyond the validated "
                    "reduction slice."
                ),
                evidence_tests=_evidence_tests(
                    "tests/ir/analytics/test_phase1_closure_contracts.py",
                    "tests/ir/analytics/test_phase_c_contracts.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="5.3",
                backbone=True,
                title="Extending the proof kernel to distributional estimands",
                benchmark_proxy=[
                    "interventional law benchmark",
                    "CDF benchmark",
                    "joint-law OT coupling sentinel",
                ],
                typed_integration_target="DistributionalEffectBundle.marginal_law_proof_ref",
                required_for_promotion=[
                    "proof-kernel support for marginal interventional law",
                    "separate coupling sidecar",
                    "no false full-ID bundle",
                ],
                scope_statement=(
                    "Phase 1 closes marginal interventional-law proofs and persists a separate "
                    "coupling sidecar so joint-law claims cannot be promoted accidentally."
                ),
                evidence_tests=_evidence_tests(
                    "tests/scientist/nodes/builtins/simulate/test_run_distributional_analysis.py",
                    "tests/scientist/test_decision_packet_distributional_econometrics.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="8.1",
                title="Algebraic model testing beyond conditional independence",
                benchmark_proxy=[
                    "trek_rank_blocker_positive",
                    "nested_verma_warning_preview",
                    "binary_iv_semialgebraic_blocker",
                ],
                typed_integration_target="CausalDiscoveryReport.algebraic_constraints",
                required_for_promotion=[
                    "trek_rank blocker severity path",
                    "nested_verma preview semantics",
                    "binary_iv semialgebraic graph-class blocker",
                ],
                scope_statement=(
                    "Phase 1 closes the declared beyond-CI algebraic families via "
                    "AlgebraicConstraintReport severity semantics and finite-sample test routes."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_constraint_discovery.py",
                    "tests/ir/analytics/test_phase1_closure_contracts.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="11.1",
                backbone=True,
                title="Machine-checkable proximal identification certificates",
                benchmark_proxy=[
                    "PCI-Core positive graph",
                    "proximal failure witnesses",
                ],
                typed_integration_target="ProofBundle.proximal_certificate_ref",
                required_for_promotion=[
                    "proximal cert persistence",
                    "ref attachment",
                    "downstream load path",
                ],
                scope_statement=(
                    "Phase 1 closes sound-but-incomplete proximal bridge certificates for the "
                    "supported PCI-Core slice."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_proximal_identify.py",
                    "tests/ir/analytics/test_phase1_closure_contracts.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="11.2",
                title="Bridge function existence and completeness conditions",
                benchmark_proxy=[
                    "bridge_feasible_positive",
                    "bridge_infeasible_bounds_fallback",
                    "weak_completeness_require_bounds",
                ],
                typed_integration_target="ProofBundle.bridge_plausibility_report_ref",
                required_for_promotion=[
                    "bridge plausibility typed persistence",
                    "proof attachment for proximal pipelines",
                    "bounds fallback integration on infeasible or weak-completeness paths",
                ],
                canonical_contract_surface="BridgePlausibilityReportRef + BoundsBundle metadata fallback",
                scope_statement=(
                    "Phase 1 closes typed bridge-plausibility diagnostics plus the canonical "
                    "bounds/negative fallback ladder when bridge existence or completeness is not "
                    "trustworthy."
                ),
                closure_state="narrow_accepted",
                boundary_reason=(
                    "The current contract formalizes a typed plausibility and fallback ladder, "
                    "not a general completeness theorem for all proximal bridge families."
                ),
                downstream_promotion_rule=(
                    "Promote proximal outputs only when bridge plausibility stays inside the "
                    "accepted diagnostic ladder; infeasible or weak-completeness cases must "
                    "resolve to bounds or negative certificates."
                ),
                kill_rule=(
                    "Do not treat bridge plausibility as a proof of general completeness or "
                    "point identification outside the accepted fallback ladder."
                ),
                evidence_tests=_evidence_tests(
                    "tests/ir/analytics/test_proximal_bridge_plausibility.py",
                    "tests/ir/analytics/test_phase1_closure_contracts.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="12.1",
                backbone=True,
                title="Recoverability certificates for proof kernel integration",
                benchmark_proxy=[
                    "four M-graph verdict cases",
                ],
                typed_integration_target="ProofBundle.recoverability_certificate_ref",
                required_for_promotion=[
                    "persist recoverability cert",
                    "persist joint decision",
                    "readiness consumption via refs",
                ],
                canonical_contract_surface=(
                    "ProofBundle.recoverability_certificate_ref + ProofBundle.joint_decision_ref"
                ),
                scope_statement=(
                    "Phase 1 closes replayable missing-data recoverability artifacts for all "
                    "currently emitted joint verdicts."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_missing_data.py",
                    "tests/ir/analytics/test_phase1_closure_contracts.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="13.1",
                backbone=True,
                title="Formal intervention type system for proof kernel",
                benchmark_proxy=[
                    "intervention hierarchy battery across all 8 supported types",
                ],
                typed_integration_target="InterventionCertificateRef",
                required_for_promotion=[
                    "query persistence",
                    "typecheck failure path",
                    "audit persistence",
                ],
                scope_statement=(
                    "Phase 1 closes the declared typed intervention family and its "
                    "persistence/audit surface."
                ),
                evidence_tests=_evidence_tests(
                    "tests/ir/analytics/test_intervention_type_system.py",
                    "tests/ir/analytics/test_phase1_closure_contracts.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="15.1",
                backbone=True,
                title="Identification conditions under DP-distorted distributions",
                benchmark_proxy=[
                    "DP graceful degradation sentinel",
                    "DP hard-block sentinel",
                ],
                typed_integration_target="DPRobustnessCertificateRef",
                required_for_promotion=[
                    "DP round-trip",
                    "proof attachment",
                    "readiness gate regression",
                ],
                scope_statement=(
                    "Phase 1 closes DP robustness attachment and readiness gating for the "
                    "declared proof classes."
                ),
                evidence_tests=_evidence_tests(
                    "tests/ir/analytics/test_dp_robustness_contract.py",
                    "tests/scientist/test_decision_packet_node_v3.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="16.1",
                backbone=True,
                title="Formal conditions for ICP-based MEC contraction",
                benchmark_proxy=[
                    "nonlinear_anm_unique_parent_recovery",
                    "redundant environment sentinel",
                    "selection_or_mixed_shift_blocker",
                ],
                typed_integration_target="RegimeShiftIdentificationCertificateRef",
                required_for_promotion=[
                    "nonlinear additive-noise identifiability witness",
                    "informative-vs-redundant environment checks",
                    "selection-or-mixed shift blocker routing",
                ],
                scope_statement=(
                    "Phase 1 certifies a nonlinear additive-noise ICP slice for continuous "
                    "policy data, with explicit environment informativeness and redundancy "
                    "conditions recorded in the certificate."
                ),
                evidence_tests=_evidence_tests(
                    "tests/ir/analytics/test_phase1_closure_contracts.py",
                    "tests/scientist/search/test_phase_d4_runtime_integration.py",
                ),
            ),
        ],
    }
)

PHASE2_CLOSURE_MANIFEST = PhaseClosureManifest.model_validate(
    {
        "phase_id": _PHASE_ID_BY_NUMBER["2"],
        "execution_intent": (
            "Use the Phase 1 contracts to widen query classes, add first production-facing "
            "theorem families, and start the first nontrivial domain upgrades."
        ),
        "phase_gate": (
            "The proof kernel, bounds layer, and discovery pipeline each gain at least one "
            "widened query family or production-facing theorem path ready for advanced integration."
        ),
        "stages": [
            _stage_declaration_data(
                stage_id="2.2",
                title="Transfer of do-calculus derivations across fragment boundaries",
                benchmark_proxy=[
                    "fragment transfer positive",
                    "cross-fragment mismatch sentinel",
                ],
                typed_integration_target="CompositionCertificate.cross_fragment_derivations",
                required_for_promotion=[
                    "derivation replay across boundaries",
                    "typed cross-fragment witness",
                    "consumer-visible transfer trace",
                ],
                scope_statement=(
                    "Phase 2 closes transfer of supported do-calculus derivations across "
                    "fragment boundaries with typed replay traces."
                ),
                evidence_tests=_evidence_tests(
                    "tests/ir/analytics/test_phase_b_contracts.py",
                    "tests/foundry/methods/catalog/causal/test_query_preservation.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="3.2",
                title="Automated bound tightening with soundness guarantees",
                benchmark_proxy=[
                    "bound tightening positive",
                    "soundness regression sentinel",
                ],
                typed_integration_target="BoundsBundle.tightening_certificate_ref",
                required_for_promotion=[
                    "sound tightening replay",
                    "certificate persistence",
                    "sharpness regression coverage",
                ],
                scope_statement=(
                    "Phase 2 closes automated tightening for supported bound families while "
                    "preserving soundness and certificate replay."
                ),
                evidence_tests=_evidence_tests(
                    "tests/ir/analytics/test_phase_b_contracts.py",
                    "tests/ir/analytics/test_phase_a_contracts.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="5.1",
                title="Causally justified OT couplings under partial identification",
                benchmark_proxy=[
                    "licensed marginal law with coupling sidecar",
                    "joint-law non-identification sentinel",
                ],
                typed_integration_target="DistributionalEffectBundle.coupling_proof_ref",
                required_for_promotion=[
                    "coupling sidecar persistence",
                    "partial-ID coupling status surface",
                    "no accidental joint-law promotion",
                ],
                scope_statement=(
                    "Phase 2 closes causally justified OT couplings only as a scoped sidecar "
                    "attached to identified or bounded marginal-law paths."
                ),
                closure_state="narrow_accepted",
                boundary_reason=(
                    "Current coupling support is intentionally sidecar-scoped and does not prove "
                    "full joint-law identification."
                ),
                downstream_promotion_rule=(
                    "Downstream consumers may use coupling diagnostics and sidecars only when the "
                    "marginal law is licensed; coupling artifacts remain explicitly separated from "
                    "joint-law claims."
                ),
                kill_rule=(
                    "Do not promote OT couplings as identified joint potential-outcome laws "
                    "without a separate theorem-backed contract."
                ),
                evidence_tests=_evidence_tests(
                    "tests/scientist/nodes/builtins/simulate/test_run_distributional_analysis.py",
                    "tests/foundry/methods/catalog/causal/test_density_ratio_distributional_ot.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="5.2",
                title="Bounded distributional effects for tail risk and subgroup shifts",
                benchmark_proxy=[
                    "lee trimming bounded path",
                    "makarov pointwise bounded path",
                    "unsupported functional sentinel",
                ],
                typed_integration_target="DistributionalEffectBundle.distributional_bounds_refs",
                required_for_promotion=[
                    "bounded functional persistence",
                    "uniformity status surface",
                    "distributional packet visibility",
                ],
                scope_statement=(
                    "Phase 2 closes bounded distributional effects for the supported Lee/Makarov "
                    "families and their downstream reporting surfaces."
                ),
                closure_state="narrow_accepted",
                boundary_reason=(
                    "Distributional bounds are theorem-backed for the supported Lee/Makarov "
                    "families, not for arbitrary distributional functionals."
                ),
                downstream_promotion_rule=(
                    "Promote bounded distributional claims only when the theorem family and "
                    "functional are listed in the persisted bounds metadata."
                ),
                kill_rule=(
                    "Do not claim theorem-backed bounds for unsupported functionals or families "
                    "outside the persisted distributional bounds contracts."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_distributional_bounds.py",
                    "tests/scientist/nodes/builtins/simulate/test_run_distributional_analysis.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="6.1",
                title="Equilibrium computation for complex strategic environments",
                benchmark_proxy=[
                    "equilibrium convergence positive",
                    "nonconvergence strategic sentinel",
                ],
                typed_integration_target="StrategicResponseBundle.equilibrium_certificate_ref",
                required_for_promotion=[
                    "equilibrium witness persistence",
                    "strategic runtime attachment",
                    "decision-packet visibility",
                ],
                scope_statement=(
                    "Phase 2 closes equilibrium computation for the supported strategic "
                    "environments and persists runtime certificates for governance."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_strategic.py",
                    "tests/scientist/governance/test_strategic_response_pass.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="7.2",
                title="Conditions for faithful micro-to-macro causal transport",
                benchmark_proxy=[
                    "faithful micro-to-macro transport positive",
                    "aggregation failure sentinel",
                ],
                typed_integration_target="AbstractionCertificate.transport_error_bound",
                required_for_promotion=[
                    "transport witness persistence",
                    "macro readiness handoff",
                    "abstraction consumption path",
                ],
                scope_statement=(
                    "Phase 2 closes faithful micro-to-macro transport certificates for supported "
                    "aggregation classes."
                ),
                evidence_tests=_evidence_tests(
                    "tests/ir/analytics/test_continuous_abstraction.py",
                    "tests/ir/analytics/test_phase_b_contracts.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="8.2",
                title="Finite-sample algebraic model testing under noise and misspecification",
                benchmark_proxy=[
                    "finite-sample trek-rank positive",
                    "misspecification blocker sentinel",
                ],
                typed_integration_target="CausalDiscoveryReport.algebraic_test_calibration",
                required_for_promotion=[
                    "finite-sample calibration",
                    "noise/misspecification warnings",
                    "governance-visible severity path",
                ],
                scope_statement=(
                    "Phase 2 closes finite-sample algebraic testing for the supported noisy and "
                    "misspecified benchmark families."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_constraint_discovery.py",
                    "tests/scientist/discovery/test_utility_judge.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="9.1",
                title="Latent variable cardinality identification from distributional shifts",
                benchmark_proxy=[
                    "latent cardinality promotion positive",
                    "underidentified shift sentinel",
                ],
                typed_integration_target="LatentPromotionVerdict.cardinality_certificate_ref",
                required_for_promotion=[
                    "cardinality witness persistence",
                    "latent governance handoff",
                    "promotion cap integration",
                ],
                scope_statement=(
                    "Phase 2 closes machine-readable latent-cardinality promotion evidence for "
                    "supported distributional-shift families."
                ),
                evidence_tests=_evidence_tests(
                    "tests/scientist/search/test_phase_d4_runtime_integration.py",
                    "tests/scientist/search/test_policy_blueprint_runtime_guards.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="9.2",
                title="Separating latent confounding, proxy mismatch, and measurement error",
                benchmark_proxy=[
                    "proxy mismatch split positive",
                    "measurement error split positive",
                    "ambiguous latent sentinel",
                ],
                typed_integration_target="LatentPromotionVerdict.failure_mode",
                required_for_promotion=[
                    "machine-readable latent split",
                    "governance-visible rationale",
                    "promotion boundary routing",
                ],
                scope_statement=(
                    "Phase 2 closes the first automatic split between latent confounding, proxy "
                    "mismatch, and measurement error for downstream promotion logic."
                ),
                evidence_tests=_evidence_tests(
                    "tests/scientist/search/test_phase_d4_runtime_integration.py",
                    "tests/scientist/search/test_policy_blueprint_runtime_guards.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="10.1",
                title="Simplicial complex identification theory for interference",
                benchmark_proxy=[
                    "pairwise honest positive",
                    "full-complex degradation sentinel",
                ],
                typed_integration_target="InterferenceCertificate.topology_scope",
                required_for_promotion=[
                    "complex topology scope persistence",
                    "pairwise fallback semantics",
                    "honest degradation route",
                ],
                scope_statement=(
                    "Phase 2 closes theorem-backed interference certificates for the supported "
                    "pairwise/cluster slice and records honest degradation for richer complexes."
                ),
                closure_state="narrow_accepted",
                boundary_reason=(
                    "The current topology lane is theorem-backed for the supported pairwise/cluster "
                    "slice, with explicit degradation from richer full-complex structures."
                ),
                downstream_promotion_rule=(
                    "Promote interference certificates only when the topology scope and degradation "
                    "status are explicitly persisted and accepted by the downstream policy path."
                ),
                kill_rule=(
                    "Do not claim full simplicial-complex identification when the runtime has "
                    "fallen back to pairwise or cluster approximations."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_interference.py",
                    "tests/foundry/methods/catalog/causal/test_interference_identification.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="12.2",
                title="Recoverability under administrative and selective missingness",
                benchmark_proxy=[
                    "administrative missingness taxonomy positive",
                    "system-change recoverability positive",
                ],
                typed_integration_target="DataReadinessReport.missingness_assessment",
                required_for_promotion=[
                    "missingness taxonomy persistence",
                    "recoverability verdict attachment",
                    "readiness consumption path",
                ],
                scope_statement=(
                    "Phase 2 closes recoverability surfaces for the declared administrative and "
                    "selective missingness families."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_missing_data.py",
                    "tests/ir/analytics/test_phase_b_contracts.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="13.2",
                title="Identification and estimation for stochastic and modified treatment policies",
                benchmark_proxy=[
                    "single-target stochastic policy positive",
                    "out-of-scope policy sentinel",
                ],
                typed_integration_target="InterventionCertificate.policy_scope",
                required_for_promotion=[
                    "stochastic policy audit persistence",
                    "policy scope encoding",
                    "downstream kill-rule surface",
                ],
                scope_statement=(
                    "Phase 2 closes stochastic and modified treatment policies for the accepted "
                    "v1 scope and records out-of-scope cases explicitly."
                ),
                closure_state="narrow_accepted",
                boundary_reason=(
                    "The current stochastic-policy lane is theorem-backed only for the accepted "
                    "v1 scope and does not yet cover arbitrary multi-target policy families."
                ),
                downstream_promotion_rule=(
                    "Promote stochastic-policy results only when the persisted policy scope is "
                    "inside the accepted v1 contract; other policies remain capped or blocked."
                ),
                kill_rule=(
                    "Do not claim general stochastic-policy identification beyond the accepted "
                    "single-target or explicitly supported policy scope."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_stochastic_policies.py",
                    "tests/ir/analytics/test_intervention_type_system.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="15.2",
                title="Conditional independence tests calibrated for DP noise",
                benchmark_proxy=[
                    "dp-noise calibrated CI positive",
                    "threshold registry regression sentinel",
                ],
                typed_integration_target="JudgeThresholdRegistry.dp_calibrated_ci_ref",
                required_for_promotion=[
                    "dp-aware CI calibration",
                    "threshold registry integration",
                    "judge runtime regression coverage",
                ],
                scope_statement=(
                    "Phase 2 closes DP-calibrated CI testing and threshold resolution without "
                    "re-implementing the already shipped DP-CI layer."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/calibration/test_dp_ci.py",
                    "tests/foundry/methods/catalog/causal/test_independence_tests.py",
                    "tests/scientist/search/test_judge_thresholds.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="16.2",
                title="Distinguishing regime shifts from latent confounding",
                benchmark_proxy=[
                    "shift-type split positive",
                    "mixed-shift blocker sentinel",
                ],
                typed_integration_target="ShiftTypeAssessment.primary_verdict",
                required_for_promotion=[
                    "shift-type assessment persistence",
                    "selection/latent routing",
                    "promotion-cap interaction",
                ],
                scope_statement=(
                    "Phase 2 closes the first regime-shift versus latent-confounding split for "
                    "downstream discovery and governance routing."
                ),
                evidence_tests=_evidence_tests(
                    "tests/scientist/search/test_phase_d4_runtime_integration.py",
                    "tests/scientist/search/test_policy_blueprint_runtime_guards.py",
                ),
            ),
        ],
    }
)

PHASE3_CLOSURE_MANIFEST = PhaseClosureManifest.model_validate(
    {
        "phase_id": _PHASE_ID_BY_NUMBER["3"],
        "execution_intent": (
            "Execute the strict dependency chains that convert the earlier theorem contracts "
            "into advanced integrated capabilities."
        ),
        "phase_gate": (
            "At least one full dependency chain in each major family reaches an "
            "implementation-grade integration specification."
        ),
        "stages": [
            _stage_declaration_data(
                stage_id="2.3",
                title="Cyclic SCM fragment composition",
                benchmark_proxy=[
                    "cyclic fragment composition positive",
                    "unsupported cycle composition sentinel",
                ],
                typed_integration_target="CompositionCertificate.dynamic_fragment_bridge_ref",
                required_for_promotion=[
                    "dynamic-semantics-anchored composition",
                    "cyclic fragment witness persistence",
                    "frontier fallback for unsupported cycles",
                ],
                scope_statement=(
                    "Phase 3 closes cyclic fragment composition for the dynamic-semantics slices "
                    "already certified upstream."
                ),
                closure_state="narrow_accepted",
                boundary_reason=(
                    "Cyclic fragment composition inherits the validated dynamic-semantics scope "
                    "and therefore remains limited to supported cyclic subclasses."
                ),
                downstream_promotion_rule=(
                    "Promote cyclic composition results only when the attached dynamic semantics "
                    "witness proves the upstream supported class."
                ),
                kill_rule=(
                    "Do not claim general cyclic fragment composition outside the validated "
                    "dynamic-semantics slice."
                ),
                evidence_tests=_evidence_tests(
                    "tests/ir/analytics/test_phase_c_contracts.py",
                    "tests/foundry/methods/catalog/causal/test_query_preservation.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="4.1",
                title="Causal semantics for rough-path and irregular sampling regimes",
                benchmark_proxy=[
                    "rough-path semantics positive",
                    "irregular sampling replay",
                ],
                typed_integration_target="ProofBundle.dynamic_semantics",
                required_for_promotion=[
                    "rough-path semantics attachment",
                    "irregular sampling replay",
                    "continuous-time consumer path",
                ],
                scope_statement=(
                    "Phase 3 closes rough-path and irregular-sampling semantics for the supported "
                    "continuous-time causal slice."
                ),
                evidence_tests=_evidence_tests(
                    "tests/ir/analytics/test_rough_path_semantics.py",
                    "tests/scientist/backtesting/test_temporal.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="4.2",
                title="Identification theory for neural SDE / neural CDE",
                benchmark_proxy=[
                    "neural SDE identification positive",
                    "unsupported neural dynamics sentinel",
                ],
                typed_integration_target="ProofBundle.dynamic_semantics",
                required_for_promotion=[
                    "neural dynamics scope encoding",
                    "dynamic proof attachment",
                    "unsupported-model blocker routing",
                ],
                scope_statement=(
                    "Phase 3 closes neural SDE/CDE identification only for the supported "
                    "continuous-time model classes anchored by the dynamic semantics contract."
                ),
                closure_state="narrow_accepted",
                boundary_reason=(
                    "Neural SDE/CDE support is limited to the current certified continuous-time "
                    "model classes and does not cover arbitrary neural dynamics."
                ),
                downstream_promotion_rule=(
                    "Promote neural dynamics results only when the dynamic semantics attachment "
                    "and model-class scope remain inside the certified slice."
                ),
                kill_rule=(
                    "Do not claim general neural SDE/CDE identification beyond the persisted "
                    "supported model-class scope."
                ),
                evidence_tests=_evidence_tests(
                    "tests/scientist/backtesting/test_temporal.py",
                    "tests/foundry/methods/catalog/causal/test_temporal_estimand_compiler.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="4.3",
                title="Conditions for valid discrete-to-continuous causal translation",
                benchmark_proxy=[
                    "discrete-to-continuous translation positive",
                    "invalid translation sentinel",
                ],
                typed_integration_target="ProofBundle.dynamic_semantics",
                required_for_promotion=[
                    "translation witness persistence",
                    "invalid-translation blocker",
                    "continuous-time consumer path",
                ],
                scope_statement=(
                    "Phase 3 closes discrete-to-continuous translation for the supported "
                    "translation classes rooted in the dynamic semantics family."
                ),
                closure_state="narrow_accepted",
                boundary_reason=(
                    "Discrete-to-continuous translation is certified only for the current "
                    "supported translation classes and explicit well-posedness checks."
                ),
                downstream_promotion_rule=(
                    "Promote translated continuous-time claims only when the translation witness "
                    "and dynamic semantics remain inside the supported classes."
                ),
                kill_rule=(
                    "Do not treat heuristic discretization bridges as proof-backed continuous-time "
                    "translations."
                ),
                evidence_tests=_evidence_tests(
                    "tests/scientist/backtesting/test_temporal.py",
                    "tests/foundry/methods/catalog/causal/test_temporal_estimand_compiler.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="4.5",
                title="Local independence and Granger-causal semantics in continuous time",
                benchmark_proxy=[
                    "local independence positive",
                    "Granger-causal semantics replay",
                ],
                typed_integration_target="ProofBundle.dynamic_semantics",
                required_for_promotion=[
                    "local independence attachment",
                    "continuous-time semantics replay",
                    "consumer-visible dynamic scope",
                ],
                scope_statement=(
                    "Phase 3 closes local-independence and Granger-causal semantics for the "
                    "supported continuous-time family."
                ),
                evidence_tests=_evidence_tests(
                    "tests/ir/analytics/test_local_independence_contract.py",
                    "tests/scientist/backtesting/test_temporal.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="6.2",
                title="Performative prediction convergence and instability",
                benchmark_proxy=[
                    "performative convergence positive",
                    "instability warning sentinel",
                ],
                typed_integration_target="PerformativeShiftSummary.stability_status",
                required_for_promotion=[
                    "convergence witness persistence",
                    "instability severity path",
                    "governance visibility",
                ],
                scope_statement=(
                    "Phase 3 closes performative convergence/instability artifacts for the "
                    "supported strategic-runtime families."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_strategic.py",
                    "tests/scientist/governance/test_strategic_response_pass.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="6.3",
                title="Decomposition of post-policy outcome into causal and strategic components",
                benchmark_proxy=[
                    "causal/strategic decomposition positive",
                    "decomposition ambiguity sentinel",
                ],
                typed_integration_target="StrategicClosureSummary.component_split",
                required_for_promotion=[
                    "component decomposition persistence",
                    "decision-packet visibility",
                    "governance consumer path",
                ],
                scope_statement=(
                    "Phase 3 closes decomposition of post-policy outcomes into causal and "
                    "strategic components for the supported strategic bundle."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_strategic.py",
                    "tests/scientist/test_decision_packet_node_v3.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="6.4",
                title="Mean Field Game equilibrium for macro-policy causal inference",
                benchmark_proxy=[
                    "MFG equilibrium positive",
                    "macro-policy fallback sentinel",
                ],
                typed_integration_target="MeanFieldEquilibriumCertificateRef",
                required_for_promotion=[
                    "MFG equilibrium persistence",
                    "macro simulation config attachment",
                    "strategic packet visibility",
                ],
                scope_statement=(
                    "Phase 3 closes the mean-field-game equilibrium lane for macro-policy causal "
                    "inference within the supported strategic family."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_strategic.py",
                    "tests/scientist/test_decision_packet_node_v3.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="7.1",
                title="Approximate abstraction error bounds for continuous and non-finite models",
                benchmark_proxy=[
                    "continuous abstraction bound positive",
                    "non-finite abstraction fallback sentinel",
                ],
                typed_integration_target="AbstractionCertificate.error_bound",
                required_for_promotion=[
                    "error bound persistence",
                    "transport handoff",
                    "abstraction certificate visibility",
                ],
                scope_statement=(
                    "Phase 3 closes approximate abstraction error bounds for the supported "
                    "continuous and non-finite abstraction families."
                ),
                evidence_tests=_evidence_tests(
                    "tests/ir/analytics/test_continuous_abstraction.py",
                    "tests/scientist/test_decision_packet_node_v3.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="8.3",
                title="Semialgebraic negative certificates and SCM class incompatibility",
                benchmark_proxy=[
                    "semialgebraic incompatibility positive",
                    "class mismatch blocker sentinel",
                ],
                typed_integration_target="NegativeCertificateRef",
                required_for_promotion=[
                    "negative certificate persistence",
                    "SCM class incompatibility semantics",
                    "discovery/governance visibility",
                ],
                scope_statement=(
                    "Phase 3 closes semialgebraic negative certificates for incompatible SCM "
                    "classes and discovery blockers."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_constraint_discovery.py",
                    "tests/ir/analytics/test_phase_f_contracts.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="10.2",
                title="Exposure-complex estimators with honest pairwise fallback",
                benchmark_proxy=[
                    "exposure-complex estimator positive",
                    "honest pairwise fallback sentinel",
                ],
                typed_integration_target="InterferenceEstimatorReport.fallback_mode",
                required_for_promotion=[
                    "fallback honesty surface",
                    "estimator persistence",
                    "reduction error consumer path",
                ],
                scope_statement=(
                    "Phase 3 closes exposure-complex estimators with explicit honest fallback "
                    "to pairwise scope when needed."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_interference_identification.py",
                    "tests/foundry/methods/catalog/causal/test_causal_engine_phase10.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="10.3",
                title="Bounds on reduction error from hypergraph to pairwise projection",
                benchmark_proxy=[
                    "hypergraph reduction bound positive",
                    "projection error sentinel",
                ],
                typed_integration_target="InterferenceReductionBoundRef",
                required_for_promotion=[
                    "reduction error persistence",
                    "pairwise fallback envelope",
                    "decision-packet visibility",
                ],
                scope_statement=(
                    "Phase 3 closes honest bounds on hypergraph-to-pairwise reduction error for "
                    "the supported interference fallback lane."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_interference_identification.py",
                    "tests/foundry/methods/catalog/causal/test_causal_engine_phase10.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="11.3",
                title="Proximal mediation and path-specific proximal effects",
                benchmark_proxy=[
                    "proximal mediation positive",
                    "proximal path-specific blocker sentinel",
                ],
                typed_integration_target="ProximalMediationCertificateRef",
                required_for_promotion=[
                    "proximal mediation persistence",
                    "path-specific proof attachment",
                    "intervention-hierarchy compatibility",
                ],
                scope_statement=(
                    "Phase 3 closes proximal mediation and path-specific proximal effects for the "
                    "supported proximal slice."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_proximal_mediation.py",
                    "tests/ir/analytics/test_proximal_bridge_plausibility.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="12.3",
                title="Compile-time recovery strategy selection",
                benchmark_proxy=[
                    "recovery strategy positive",
                    "unsupported recovery sentinel",
                ],
                typed_integration_target="RecoveryStrategyDecisionRef",
                required_for_promotion=[
                    "strategy selection persistence",
                    "recoverability contract reuse",
                    "readiness/governance handoff",
                ],
                scope_statement=(
                    "Phase 3 closes compile-time recovery strategy selection for the supported "
                    "recoverability families."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_recovery_strategy_selector.py",
                    "tests/foundry/methods/catalog/causal/test_missing_data.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="13.3",
                title="Path-specific and edge-specific effect identification at scale",
                benchmark_proxy=[
                    "path-specific positive",
                    "edge-specific positive",
                    "unsupported path policy sentinel",
                ],
                typed_integration_target="PathSpecificEffectCertificateRef",
                required_for_promotion=[
                    "path-specific persistence",
                    "edge-specific audit path",
                    "intervention hierarchy integration",
                ],
                scope_statement=(
                    "Phase 3 closes path-specific and edge-specific effect identification for "
                    "the supported scaled intervention families."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_path_specific_identify.py",
                    "tests/foundry/methods/catalog/causal/test_stochastic_policies.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="15.3",
                title="Transportability and recoverability under DP distortion",
                benchmark_proxy=[
                    "dp transportability positive",
                    "dp recoverability positive",
                    "dp hard-block sentinel",
                ],
                typed_integration_target="PrivacyTransportabilityCertificateRef",
                required_for_promotion=[
                    "dp transportability persistence",
                    "recoverability interaction surface",
                    "readiness/governance visibility",
                ],
                scope_statement=(
                    "Phase 3 closes transportability and recoverability under DP distortion for "
                    "the supported privacy-aware proof families."
                ),
                evidence_tests=_evidence_tests(
                    "tests/ir/analytics/test_privacy_transportability_contract.py",
                    "tests/scientist/test_decision_packet_node_v3.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="16.3",
                title="Computational tractability and Foundry integration",
                benchmark_proxy=[
                    "tractable shift pipeline positive",
                    "integration complexity sentinel",
                ],
                typed_integration_target="ShiftTypeAssessment.integration_status",
                required_for_promotion=[
                    "tractability budget surface",
                    "Foundry integration attachment",
                    "policy/governance routing",
                ],
                scope_statement=(
                    "Phase 3 closes computational tractability and Foundry integration for the "
                    "regime-shift pipeline."
                ),
                evidence_tests=_evidence_tests(
                    "tests/scientist/search/test_phase_d4_runtime_integration.py",
                    "tests/scientist/test_causal_full_workflow_guard.py",
                ),
            ),
        ],
    }
)

PHASE4_CLOSURE_MANIFEST = PhaseClosureManifest.model_validate(
    {
        "phase_id": _PHASE_ID_BY_NUMBER["4"],
        "execution_intent": (
            "Close the loop on latent promotion, compositional completeness, advanced recourse "
            "geometry, and the long-horizon operator/kernel frontier."
        ),
        "phase_gate": (
            "Long-horizon tracks either graduate into narrow theorem-backed implementation scopes "
            "or are honestly narrowed, deferred, or refused with explicit promotion rules."
        ),
        "stages": [
            _stage_declaration_data(
                stage_id="2.4",
                title="Automatic latent bridge synthesis",
                benchmark_proxy=[
                    "latent bridge synthesis positive",
                    "promotion boundary sentinel",
                ],
                typed_integration_target="CompositionCertificate.latent_bridge_ref",
                required_for_promotion=[
                    "latent bridge synthesis persistence",
                    "promotion-boundary routing",
                    "consumer-visible latent bridge scope",
                ],
                scope_statement=(
                    "Phase 4 closes automatic latent bridge synthesis for the promoted latent "
                    "artifact families that survive earlier gates."
                ),
                evidence_tests=_evidence_tests(
                    "tests/ir/analytics/test_phase_b_contracts.py",
                    "tests/scientist/search/test_phase_d4_runtime_integration.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="2.5",
                title="Category-theoretic completeness",
                benchmark_proxy=[
                    "exact observed DAG adjustment positive",
                    "non-completeness boundary sentinel",
                ],
                typed_integration_target="CrossGraphCompletenessCertificate.scope",
                required_for_promotion=[
                    "machine-readable completeness scope",
                    "non-completeness classification",
                    "downstream theorem-claim guard",
                ],
                scope_statement=(
                    "Phase 4 closes category-theoretic completeness doc-faithfully by encoding the "
                    "accepted theorem scope and machine-readable non-completeness boundaries."
                ),
                closure_state="narrow_accepted",
                boundary_reason=(
                    "The current completeness theorem is explicitly scoped to "
                    "`exact_observed_dag_adjustment_v1`; broader families remain non-complete."
                ),
                downstream_promotion_rule=(
                    "Promote completeness claims only when the persisted completeness scope equals "
                    "the accepted theorem-backed subclass."
                ),
                kill_rule=(
                    "Do not surface engineering-preserved results as theorem-backed completeness "
                    "outside `exact_observed_dag_adjustment_v1`."
                ),
                evidence_tests=_evidence_tests(
                    "tests/ir/analytics/test_phase_b_contracts.py",
                    "tests/foundry/methods/catalog/causal/test_query_preservation.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="9.3",
                title="Promotion criteria for latent artifacts above PROOF_ONLY",
                benchmark_proxy=[
                    "latent promotion positive",
                    "proof-only cap sentinel",
                ],
                typed_integration_target="LatentPromotionVerdict.promotion_level",
                required_for_promotion=[
                    "promotion verdict persistence",
                    "readiness-cap interaction",
                    "human-gate routing",
                ],
                scope_statement=(
                    "Phase 4 closes promotion criteria for latent artifacts above PROOF_ONLY via "
                    "machine-readable promotion verdicts and governance caps."
                ),
                evidence_tests=_evidence_tests(
                    "tests/scientist/search/test_policy_blueprint_runtime_guards.py",
                    "tests/scientist/search/test_phase_d4_runtime_integration.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="13.4",
                title="Optimal recourse intervention and causal manifold geometry",
                benchmark_proxy=[
                    "optimal recourse positive",
                    "causal manifold geometry positive",
                ],
                typed_integration_target="RecourseGeometryCertificateRef",
                required_for_promotion=[
                    "recourse geometry persistence",
                    "policy design visibility",
                    "intervention hierarchy reuse",
                ],
                scope_statement=(
                    "Phase 4 closes optimal recourse and causal-manifold geometry for the "
                    "supported recourse policy families."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_path_specific_identify.py",
                    "tests/scientist/test_decision_packet_node_v3.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="14.1",
                title="Kernel causal effect operators with identification guarantees",
                benchmark_proxy=[
                    "kernel lowering ready positive",
                    "distributional operator lowering sentinel",
                ],
                typed_integration_target="EvidenceBundle.kernel_estimator_spec_ref",
                required_for_promotion=[
                    "kernel estimator spec persistence",
                    "operator lift scope encoding",
                    "scientist sink visibility",
                ],
                scope_statement=(
                    "Phase 4 closes kernel causal effect operators with persisted lowering "
                    "contracts and downstream visibility in scientist sinks."
                ),
                evidence_tests=_evidence_tests(
                    "tests/ir/analytics/test_kernel_causal_contract.py",
                    "tests/foundry/methods/catalog/causal/test_kernel_runtime.py",
                ),
            ),
            _stage_declaration_data(
                stage_id="14.2",
                title="Operator-valued regression for multi-output causal effects",
                benchmark_proxy=[
                    "operator-valued multi-output positive",
                    "unsupported operator scope sentinel",
                ],
                typed_integration_target="OperatorEffectBundleRef",
                required_for_promotion=[
                    "operator-valued bundle persistence",
                    "kernel/operator summary in scientist sink",
                    "unsupported-scope limitation surface",
                ],
                scope_statement=(
                    "Phase 4 closes operator-valued regression for supported multi-output causal "
                    "effects and surfaces its scope in scientist decision artifacts."
                ),
                evidence_tests=_evidence_tests(
                    "tests/foundry/methods/catalog/causal/test_operator_valued_methods.py",
                    "tests/foundry/methods/catalog/causal/test_operator_estimand_compiler.py",
                ),
            ),
        ],
    }
)

ALL_PHASE_CLOSURE_MANIFESTS: tuple[PhaseClosureManifest, ...] = (
    PHASE1_CLOSURE_MANIFEST,
    PHASE2_CLOSURE_MANIFEST,
    PHASE3_CLOSURE_MANIFEST,
    PHASE4_CLOSURE_MANIFEST,
)


def all_phase_closure_manifests() -> tuple[PhaseClosureManifest, ...]:
    """Return all checked-in phase manifests in phase order."""

    return ALL_PHASE_CLOSURE_MANIFESTS


def all_stage_declarations() -> tuple[PhaseStageDeclaration, ...]:
    """Return the stage declarations across all phases in manifest order."""

    return tuple(stage for manifest in ALL_PHASE_CLOSURE_MANIFESTS for stage in manifest.stages)


def phase_stage_declaration(phase_id: str, stage_id: str) -> PhaseStageDeclaration:
    """Return the declaration for ``stage_id`` inside ``phase_id``."""

    resolved_phase_id = _clean_stage_token(phase_id, field_name="phase_id")
    resolved_stage_id = _clean_stage_token(stage_id, field_name="stage_id")
    manifest = next(
        (item for item in ALL_PHASE_CLOSURE_MANIFESTS if item.phase_id == resolved_phase_id), None
    )
    if manifest is None:
        raise KeyError(f"Unknown phase_id: {resolved_phase_id}")
    try:
        return manifest.stage_map()[resolved_stage_id]
    except KeyError as exc:
        raise KeyError(
            f"Unknown stage_id {resolved_stage_id!r} for phase {resolved_phase_id!r}"
        ) from exc


def stage_declaration(stage_id: str) -> tuple[str, PhaseStageDeclaration]:
    """Return ``(phase_id, declaration)`` for the given stage id."""

    resolved_stage_id = _clean_stage_token(stage_id, field_name="stage_id")
    for manifest in ALL_PHASE_CLOSURE_MANIFESTS:
        declaration = manifest.stage_map().get(resolved_stage_id)
        if declaration is not None:
            return manifest.phase_id, declaration
    raise KeyError(f"Unknown stage_id: {resolved_stage_id}")


def phase1_stage_declaration(stage_id: str) -> PhaseStageDeclaration:
    """Return the checked-in Phase 1 declaration for one stage."""

    return phase_stage_declaration(PHASE1_CLOSURE_MANIFEST.phase_id, stage_id)


def materialize_phase1_frontier_sketch(
    *,
    stage_id: str,
    family: str,
    sketch_type: str,
    hypothesis: str,
    primary_ref: ArtifactRefModel | None = None,
    known_limitations: tuple[str, ...] | list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> FrontierSketch:
    """Materialize a frontier sketch linked to the checked-in Phase 1 declaration."""

    declaration = phase1_stage_declaration(stage_id)
    limitations = tuple(known_limitations or ("promotion checklist incomplete",))
    return FrontierSketch(
        stage_id=declaration.stage_id,
        family=family,
        sketch_type=sketch_type,
        hypothesis=hypothesis,
        benchmark_proxy=declaration.benchmark_proxy,
        typed_integration_target=declaration.typed_integration_target,
        known_limitations=limitations,
        required_for_promotion=declaration.required_for_promotion,
        primary_ref=primary_ref,
        canonical_contract_surface=declaration.canonical_contract_surface,
        metadata={
            "title": declaration.title,
            "scope_statement": declaration.scope_statement,
            "closure_state": declaration.closure_state,
            **dict(metadata or {}),
        },
    )


def persist_frontier_sketch(
    store: ArtifactStore,
    sketch: FrontierSketch,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.frontier_sketch",
    schema_version: str = "1.0",
) -> FrontierSketchRef:
    """Persist a frontier sketch and return its typed artifact ref."""

    ref = put_json_artifact(
        store,
        sketch.model_dump(mode="json"),
        kind="ir.frontier_sketch",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return FrontierSketchRef.model_validate(ref)


def load_frontier_sketch(
    store: ArtifactStore,
    ref: FrontierSketchRef,
) -> FrontierSketch:
    """Load a persisted frontier sketch."""

    payload = get_json_artifact(store, ref.artifact_id)
    return FrontierSketch.model_validate(payload)


def parse_research_plan_stage_index(
    plan_path: str | Path | None = None,
) -> tuple[dict[str, DocumentStageEntry], dict[str, tuple[str, ...]]]:
    """Parse the source plan and return first-occurrence stage headings plus duplicates."""

    resolved_plan_path = (
        Path(plan_path) if plan_path is not None else _default_repo_root() / _DEFAULT_PLAN_DOC_PATH
    )
    lines = resolved_plan_path.read_text(encoding="utf-8").splitlines()
    stage_entries: dict[str, DocumentStageEntry] = {}
    duplicates: dict[str, list[str]] = {}
    current_phase_id: str | None = None
    for line_number, line in enumerate(lines, start=1):
        phase_match = _PHASE_HEADING_PATTERN.match(line)
        if phase_match is not None:
            current_phase_id = _PHASE_ID_BY_NUMBER.get(phase_match.group("number"))
            continue
        stage_match = _STAGE_HEADING_PATTERN.match(line)
        if stage_match is None or current_phase_id is None:
            continue
        stage_id = stage_match.group("stage_id")
        title = stage_match.group("title").strip()
        location = f"{current_phase_id}:{line_number}"
        if stage_id not in stage_entries:
            stage_entries[stage_id] = DocumentStageEntry(
                stage_id=stage_id,
                title=title,
                phase_id=current_phase_id,
                source_line=line_number,
            )
            continue
        duplicates.setdefault(stage_id, []).append(location)
    return stage_entries, {stage_id: tuple(items) for stage_id, items in duplicates.items()}


def build_phase_closure_validation_report(
    *,
    repo_root: str | Path | None = None,
    previous_snapshot: str | Path | None = None,
) -> PhaseClosureValidationReport:
    """Validate the checked-in manifests and evidence paths against the repo."""

    resolved_repo_root = Path(repo_root) if repo_root is not None else _default_repo_root()
    resolved_repo_root = resolved_repo_root.resolve()
    plan_path = resolved_repo_root / _DEFAULT_PLAN_DOC_PATH
    document_stage_entries, duplicate_document_stages = parse_research_plan_stage_index(plan_path)
    manifest_stage_map: dict[str, tuple[str, PhaseStageDeclaration]] = {}
    issues: list[PhaseClosureValidationIssue] = []

    for manifest in ALL_PHASE_CLOSURE_MANIFESTS:
        for stage in manifest.stages:
            if stage.stage_id in manifest_stage_map:
                issues.append(
                    PhaseClosureValidationIssue(
                        severity="error",
                        code="duplicate_manifest_stage_id",
                        stage_id=stage.stage_id,
                        phase_id=manifest.phase_id,
                        message=f"Stage {stage.stage_id} appears more than once across manifests.",
                    )
                )
                continue
            manifest_stage_map[stage.stage_id] = (manifest.phase_id, stage)

    for stage_id, document_entry in document_stage_entries.items():
        manifest_entry = manifest_stage_map.get(stage_id)
        if manifest_entry is None:
            issues.append(
                PhaseClosureValidationIssue(
                    severity="error",
                    code="missing_stage_manifest",
                    stage_id=stage_id,
                    phase_id=document_entry.phase_id,
                    message=f"Document stage {stage_id} is missing from checked-in manifests.",
                    path=_DEFAULT_PLAN_DOC_PATH,
                )
            )
            continue
        manifest_phase_id, stage = manifest_entry
        if manifest_phase_id != document_entry.phase_id:
            issues.append(
                PhaseClosureValidationIssue(
                    severity="error",
                    code="phase_mismatch",
                    stage_id=stage_id,
                    phase_id=manifest_phase_id,
                    message=(
                        f"Stage {stage_id} is declared under {manifest_phase_id} but the first "
                        f"document occurrence is in {document_entry.phase_id}."
                    ),
                    path=_DEFAULT_PLAN_DOC_PATH,
                )
            )
        if stage.title != document_entry.title:
            issues.append(
                PhaseClosureValidationIssue(
                    severity="error",
                    code="title_mismatch",
                    stage_id=stage_id,
                    phase_id=manifest_phase_id,
                    message=(
                        f"Stage {stage_id} title mismatch: manifest={stage.title!r}, "
                        f"document={document_entry.title!r}."
                    ),
                    path=_DEFAULT_PLAN_DOC_PATH,
                )
            )

    for stage_id, (phase_id, _) in manifest_stage_map.items():
        if stage_id not in document_stage_entries:
            issues.append(
                PhaseClosureValidationIssue(
                    severity="error",
                    code="extra_manifest_stage",
                    stage_id=stage_id,
                    phase_id=phase_id,
                    message=f"Manifest stage {stage_id} is not present in the source plan.",
                )
            )

    for stage_id, _locations in duplicate_document_stages.items():
        issues.append(
            PhaseClosureValidationIssue(
                severity="info",
                code="duplicate_document_stage_heading",
                stage_id=stage_id,
                message=(
                    f"Stage {stage_id} appears multiple times in the plan document; the validator "
                    "uses the first occurrence as the source of truth."
                ),
                path=_DEFAULT_PLAN_DOC_PATH,
            )
        )

    stage_issue_codes: dict[str, list[str]] = {}
    missing_paths_by_stage: dict[str, list[str]] = {}
    stage_results: list[StageClosureValidationResult] = []
    phase_status: dict[str, ValidationStatus] = {
        manifest.phase_id: "complete" for manifest in ALL_PHASE_CLOSURE_MANIFESTS
    }

    for manifest in ALL_PHASE_CLOSURE_MANIFESTS:
        for stage in manifest.stages:
            for relative_path in (*stage.evidence_tests, *stage.evidence_docs):
                candidate = resolved_repo_root / relative_path
                if candidate.exists():
                    continue
                issues.append(
                    PhaseClosureValidationIssue(
                        severity="error",
                        code="missing_evidence_path",
                        stage_id=stage.stage_id,
                        phase_id=manifest.phase_id,
                        message=f"Evidence path is missing: {relative_path}",
                        path=relative_path,
                    )
                )
                missing_paths_by_stage.setdefault(stage.stage_id, []).append(relative_path)

    for issue in issues:
        if issue.stage_id is not None:
            stage_issue_codes.setdefault(issue.stage_id, []).append(issue.code)
        if issue.phase_id is not None and issue.severity == "error":
            phase_status[issue.phase_id] = "incomplete"

    for manifest in ALL_PHASE_CLOSURE_MANIFESTS:
        for stage in manifest.stages:
            missing_paths = tuple(missing_paths_by_stage.get(stage.stage_id, ()))
            issue_codes = tuple(stage_issue_codes.get(stage.stage_id, ()))
            status: ValidationStatus = (
                "incomplete"
                if any(code != "duplicate_document_stage_heading" for code in issue_codes if code)
                else "complete"
            )
            if missing_paths:
                status = "incomplete"
            stage_results.append(
                StageClosureValidationResult(
                    phase_id=manifest.phase_id,
                    stage_id=stage.stage_id,
                    title=stage.title,
                    closure_state=stage.closure_state,
                    status=status,
                    typed_integration_target=stage.typed_integration_target,
                    canonical_contract_surface=stage.canonical_contract_surface,
                    benchmark_proxy=stage.benchmark_proxy,
                    evidence_tests=stage.evidence_tests,
                    evidence_docs=stage.evidence_docs,
                    evidence_contracts=stage.evidence_contracts,
                    missing_paths=missing_paths,
                    issue_codes=issue_codes,
                )
            )
            if status == "incomplete":
                phase_status[manifest.phase_id] = "incomplete"

    regression: dict[str, Any] = {}
    if previous_snapshot is not None:
        snapshot_path = Path(previous_snapshot)
        if snapshot_path.exists():
            try:
                previous_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
                previous_stage_status = {
                    item["stage_id"]: item["status"]
                    for item in previous_payload.get("stage_results", [])
                    if isinstance(item, dict)
                }
                changed = [
                    result.stage_id
                    for result in stage_results
                    if previous_stage_status.get(result.stage_id) != result.status
                ]
                if changed:
                    regression["changed_stage_status"] = changed
            except (OSError, ValueError, TypeError, KeyError):
                regression["previous_snapshot_parse_failed"] = str(snapshot_path)

    overall_status: ValidationStatus = (
        "incomplete"
        if any(issue.severity == "error" for issue in issues)
        or any(result.status == "incomplete" for result in stage_results)
        else "complete"
    )
    return PhaseClosureValidationReport(
        source_document=_DEFAULT_PLAN_DOC_PATH,
        repo_root=str(resolved_repo_root),
        overall_status=overall_status,
        phase_status=phase_status,
        stage_results=tuple(stage_results),
        issues=tuple(issues),
        duplicate_document_stages=duplicate_document_stages,
        regression=regression,
    )


__all__ = [
    "ALL_PHASE_CLOSURE_MANIFESTS",
    "PHASE1_CLOSURE_MANIFEST",
    "PHASE2_CLOSURE_MANIFEST",
    "PHASE3_CLOSURE_MANIFEST",
    "PHASE4_CLOSURE_MANIFEST",
    "DocumentStageEntry",
    "FrontierSketch",
    "FrontierSketchRef",
    "PhaseClosureManifest",
    "PhaseClosureValidationIssue",
    "PhaseClosureValidationReport",
    "PhaseStageDeclaration",
    "StageClosureValidationResult",
    "all_phase_closure_manifests",
    "all_stage_declarations",
    "build_phase_closure_validation_report",
    "load_frontier_sketch",
    "materialize_phase1_frontier_sketch",
    "parse_research_plan_stage_index",
    "persist_frontier_sketch",
    "phase1_stage_declaration",
    "phase_stage_declaration",
    "stage_declaration",
]
