"""Phase-closure frontier artifacts and manifest declarations.

Phase 1 explicitly requires machine-checkable benchmark proxies, typed
integration targets, and promotion checklists for each backbone stage. This
module turns those document requirements into persisted IR contracts that can
be attached to proof bundles whenever a stage is intentionally scope-limited
or still waiting on later promotion work.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import FrontierSketchRef

from ..refs import ArtifactRefModel


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


class PhaseStageDeclaration(BaseModel):
    """Checked-in declaration for one phase stage and its closure contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stage_id: str
    title: str
    benchmark_proxy: tuple[str, ...]
    typed_integration_target: str
    required_for_promotion: tuple[str, ...]
    canonical_contract_surface: str
    scope_statement: str

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

    @field_validator("benchmark_proxy", "required_for_promotion", mode="before")
    @classmethod
    def _validate_non_empty_items(cls, value: object, info: Any) -> tuple[str, ...]:
        return _clean_non_empty_list(value, field_name=str(info.field_name))


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
            item if isinstance(item, PhaseStageDeclaration) else PhaseStageDeclaration.model_validate(item)
            for item in value
        )
        if not stages:
            raise ValueError("stages must be non-empty")
        return stages

    @model_validator(mode="after")
    def _validate_unique_stage_ids(self) -> "PhaseClosureManifest":
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


PHASE1_CLOSURE_MANIFEST = PhaseClosureManifest.model_validate(
    {
        "phase_id": "phase_1_first_production_unlocks_and_certificate_foundations",
        "execution_intent": (
            "Create the first machine-checkable theorem/certificate contracts that directly "
            "unlock production integration and anchor later phases."
        ),
        "phase_gate": (
            "Every stage has a benchmark proxy, a typed integration target, and a concrete "
            "proof/certificate contract consumable by downstream phases."
        ),
        "stages": [
            {
                "stage_id": "2.1",
                "title": "Latent projection and query preservation",
                "benchmark_proxy": [
                    "latent front-door positive case",
                    "hedge counterexample",
                    "unresolved latent sentinel",
                ],
                "typed_integration_target": "CompositionCertificate.query_certificates",
                "required_for_promotion": [
                    "exact latent-projection replay",
                    "persisted negative witness",
                    "scientist consumer path",
                ],
                "canonical_contract_surface": "CompositionCertificate.query_certificates",
                "scope_statement": (
                    "Phase 1 closes latent-preservation certificates for supported reconciliation paths."
                ),
            },
            {
                "stage_id": "3.1",
                "title": "Partial identification dual certificates",
                "benchmark_proxy": [
                    "known sharp LP family",
                    "non-sharp relaxed family sentinel",
                ],
                "typed_integration_target": "BoundsBundle.dual_certificate_ref",
                "required_for_promotion": [
                    "dual validation",
                    "CAS round-trip",
                    "sharpness_status recompute",
                ],
                "canonical_contract_surface": "BoundsBundle.dual_certificate_ref",
                "scope_statement": (
                    "Phase 1 closes LP-backed dual certificates for supported exact and relaxed bound families."
                ),
            },
            {
                "stage_id": "4.4",
                "title": "Scoped cyclic sigma-separation certificates",
                "benchmark_proxy": [
                    "stable reducible cycle",
                    "sigma-fail sentinel",
                    "non-well-posed cycle",
                ],
                "typed_integration_target": "ProofBundle.dynamic_semantics",
                "required_for_promotion": [
                    "validated reduction class",
                    "well-posedness witness",
                    "explicit boundary artifact for unsupported cycles",
                ],
                "canonical_contract_surface": "ProofBundle.dynamic_semantics",
                "scope_statement": (
                    "Phase 1 only certifies validated linear-unique cyclic reductions; unsupported cycles remain frontier scoped."
                ),
            },
            {
                "stage_id": "5.3",
                "title": "Distributional marginal-law proof contracts",
                "benchmark_proxy": [
                    "interventional law benchmark",
                    "CDF benchmark",
                    "joint-law OT coupling sentinel",
                ],
                "typed_integration_target": "DistributionalEffectBundle.marginal_law_proof_ref",
                "required_for_promotion": [
                    "proof-kernel support for marginal interventional law",
                    "separate coupling sidecar",
                    "no false full-ID bundle",
                ],
                "canonical_contract_surface": "DistributionalEffectBundle.marginal_law_proof_ref",
                "scope_statement": (
                    "Phase 1 closes marginal interventional-law proofs only; couplings and joint laws stay scenario/frontier scoped."
                ),
            },
            {
                "stage_id": "11.1",
                "title": "Proximal bridge certificate persistence",
                "benchmark_proxy": [
                    "PCI-Core positive graph",
                    "proximal failure witnesses",
                ],
                "typed_integration_target": "ProofBundle.proximal_certificate_ref",
                "required_for_promotion": [
                    "proximal cert persistence",
                    "ref attachment",
                    "downstream load path",
                ],
                "canonical_contract_surface": "ProofBundle.proximal_certificate_ref",
                "scope_statement": (
                    "Phase 1 closes sound-but-incomplete proximal bridge certificates for the supported PCI-Core slice."
                ),
            },
            {
                "stage_id": "12.1",
                "title": "Recoverability and joint-decision artifacts",
                "benchmark_proxy": [
                    "four M-graph verdict cases",
                ],
                "typed_integration_target": "ProofBundle.recoverability_certificate_ref",
                "required_for_promotion": [
                    "persist recoverability cert",
                    "persist joint decision",
                    "readiness consumption via refs",
                ],
                "canonical_contract_surface": (
                    "ProofBundle.recoverability_certificate_ref + ProofBundle.joint_decision_ref"
                ),
                "scope_statement": (
                    "Phase 1 closes replayable missing-data recoverability artifacts for all currently emitted joint verdicts."
                ),
            },
            {
                "stage_id": "13.1",
                "title": "Typed intervention proof kernel",
                "benchmark_proxy": [
                    "intervention hierarchy battery across all 8 supported types",
                ],
                "typed_integration_target": "InterventionCertificateRef",
                "required_for_promotion": [
                    "query persistence",
                    "typecheck failure path",
                    "audit persistence",
                ],
                "canonical_contract_surface": "InterventionCertificateRef",
                "scope_statement": (
                    "Phase 1 closes the declared typed intervention family and its persistence/audit surface."
                ),
            },
            {
                "stage_id": "15.1",
                "title": "DP robustness certificate attachment",
                "benchmark_proxy": [
                    "DP graceful degradation sentinel",
                    "DP hard-block sentinel",
                ],
                "typed_integration_target": "DPRobustnessCertificateRef",
                "required_for_promotion": [
                    "DP round-trip",
                    "proof attachment",
                    "readiness gate regression",
                ],
                "canonical_contract_surface": "DPRobustnessCertificateRef",
                "scope_statement": (
                    "Phase 1 closes DP robustness attachment and readiness gating for the declared proof classes."
                ),
            },
            {
                "stage_id": "16.1",
                "title": "Regime-shift linear ICP proxy contract",
                "benchmark_proxy": [
                    "linear regime-shift discovery benchmark",
                    "redundant environment sentinel",
                ],
                "typed_integration_target": "RegimeShiftIdentificationCertificateRef",
                "required_for_promotion": [
                    "explicit linear proxy scope",
                    "informative-vs-redundant environment checks",
                    "nonlinear promotion checklist",
                ],
                "canonical_contract_surface": "RegimeShiftIdentificationCertificateRef",
                "scope_statement": (
                    "Phase 1 only certifies the linear ICP proxy surface; nonlinear/general guarantees remain promotion work."
                ),
            },
        ],
    }
)


def phase1_stage_declaration(stage_id: str) -> PhaseStageDeclaration:
    """Return the checked-in Phase 1 declaration for one stage."""

    resolved_stage_id = _clean_stage_token(stage_id, field_name="stage_id")
    try:
        return PHASE1_CLOSURE_MANIFEST.stage_map()[resolved_stage_id]
    except KeyError as exc:
        raise KeyError(f"Unknown Phase 1 stage_id: {resolved_stage_id}") from exc


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
    limitations = tuple(
        known_limitations
        or (
            "promotion checklist incomplete",
        )
    )
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


__all__ = [
    "FrontierSketch",
    "FrontierSketchRef",
    "PHASE1_CLOSURE_MANIFEST",
    "PhaseClosureManifest",
    "PhaseStageDeclaration",
    "load_frontier_sketch",
    "materialize_phase1_frontier_sketch",
    "persist_frontier_sketch",
    "phase1_stage_declaration",
]
