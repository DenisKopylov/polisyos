"""Describe discovery outputs, latent-assumption disclosures, and algebraic diagnostics."""
from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.ir.analytics.invariance import RegimeShiftIdentificationCertificate
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import ArtifactRefModel, CausalDiscoveryReportRef

_ALGEBRAIC_IMPLIED_CONSTRAINTS_KIND = "ir.algebraic_implied_constraints"
_ALGEBRAIC_IMPLIED_CONSTRAINTS_SCHEMA_NAME = "ir.algebraic_implied_constraints"
_ALGEBRAIC_VIOLATED_CONSTRAINTS_KIND = "ir.algebraic_violated_constraints"
_ALGEBRAIC_VIOLATED_CONSTRAINTS_SCHEMA_NAME = "ir.algebraic_violated_constraints"
_ALGORITHMIC_ALGEBRAIC_GEOMETRY_METHODS = frozenset(
    {
        "iv_binary_response_polytope",
        "iv_binary_instrumental_inequalities",
    }
)
LATENT_CARDINALITY_EVIDENCE_KEY = "latent_cardinality_evidence"
LATENT_CARDINALITY_FAILURE_REASONS_KEY = "latent_cardinality_failure_reasons"


class AlgebraicConstraintFamily(str, Enum):
    """Select the family of algebraic test implied by a graph or latent-factor block."""
    CI = "ci"
    TETRAD = "tetrad"
    OVERCOMPLETE = "overcomplete"
    TREK_RANK = "trek_rank"
    NESTED_VERMA = "nested_verma"
    ALGEBRAIC_GEOMETRY_INVARIANT = "algebraic_geometry_invariant"


class AlgebraicAssumptionRegime(str, Enum):
    """Declare the statistical regime assumed by one algebraic constraint family."""

    LINEAR_GAUSSIAN_CONTINUOUS = "linear_gaussian_continuous"
    DISCRETE_NESTED = "discrete_nested"
    GAUSSIAN_NESTED = "gaussian_nested"
    UNSPECIFIED = "unspecified"


class AlgebraicTestMode(str, Enum):
    """Choose the concrete finite-sample calibration route used for one block."""

    LR = "lr"
    WALD = "wald"
    SCORE = "score"
    BOOTSTRAP_MINOR = "bootstrap_minor"
    BOOTSTRAP_RANK = "bootstrap_rank"
    OFFLINE_CATALOG = "offline_catalog"
    RESEARCH_PREVIEW = "research_preview"


class NestedMarkovModelFamily(str, Enum):
    """Restrict a nested/Verma constraint to one fitted supermodel family."""

    DISCRETE_NESTED = "discrete_nested"
    GAUSSIAN_NESTED = "gaussian_nested"


class AlgebraicAssumptionStatus(str, Enum):
    """Describe whether a constraint's declared assumptions matched the observed regime."""

    DECLARED = "declared"
    VALIDATED = "validated"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


class AlgebraicRegularityStatus(str, Enum):
    """Summarize whether the test operated in a regular or potentially singular regime."""

    REGULAR = "regular"
    POTENTIALLY_SINGULAR = "potentially_singular"
    IRREGULAR = "irregular"
    UNKNOWN = "unknown"


class AlgebraicNullDistribution(str, Enum):
    """Record the null distribution family used to calibrate an algebraic test."""

    ANALYTIC = "analytic"
    ASYMPTOTIC = "asymptotic"
    BOOTSTRAP = "bootstrap"
    RESEARCH_PREVIEW = "research_preview"
    UNKNOWN = "unknown"


class AlgebraicCalibrationMode(str, Enum):
    """Capture the calibration route attached to one evaluated constraint."""

    ANALYTIC = "analytic"
    BOOTSTRAP = "bootstrap"
    PARAMETRIC_BOOTSTRAP = "parametric_bootstrap"
    HOLDOUT = "holdout"
    RESEARCH_PREVIEW = "research_preview"
    UNKNOWN = "unknown"


class AlgebraicFalsificationScope(str, Enum):
    """Clarify which claim a failed algebraic test actually falsifies."""

    GRAPH_CLASS = "graph_class"
    EDGE_LOCAL = "edge_local"
    RANKING_ONLY = "ranking_only"
    MEASUREMENT_BLOCK = "measurement_block"
    UNKNOWN = "unknown"


class AlgebraicReproducibilityTier(str, Enum):
    """Describe whether the evaluation was deterministic, resampled, or preview-only."""

    DETERMINISTIC = "deterministic"
    STOCHASTIC_BOOTSTRAP = "stochastic_bootstrap"
    RESEARCH_PREVIEW = "research_preview"
    UNKNOWN = "unknown"


class AlgebraicBlockSpec(BaseModel):
    """Declare one variable block whose implied algebraic constraints should be tested."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    block_id: str = Field(min_length=1)
    family: AlgebraicConstraintFamily
    variables: tuple[str, ...]
    quadruples: tuple[tuple[str, str, str, str], ...] = ()
    expected_rank: int | None = Field(default=None, ge=1)
    max_residual_energy: float | None = Field(default=None, ge=0.0)
    row_variables: tuple[str, ...] = ()
    col_variables: tuple[str, ...] = ()
    max_rank: int | None = Field(default=None, ge=0)
    graph_scope: str | None = Field(default=None, min_length=1)
    left_choke_set: tuple[str, ...] = ()
    right_choke_set: tuple[str, ...] = ()
    assumption_regime: AlgebraicAssumptionRegime | None = None
    test_mode: AlgebraicTestMode | None = None
    cadmg_scope: str | None = Field(default=None, min_length=1)
    fixing_sequence: tuple[str, ...] = ()
    kernel_statement: str | None = Field(default=None, min_length=1)
    identified_kernel_ref: ArtifactRefModel | None = None
    positivity_required: bool | None = None
    model_family: NestedMarkovModelFamily | None = None
    invariant_polynomials: tuple[str, ...] = ()
    semi_algebraic_inequalities: tuple[str, ...] = ()
    derivation_method: str | None = Field(default=None, min_length=1)
    certificate_ref: ArtifactRefModel | None = None
    precomputed_violation_score: float | None = Field(default=None, ge=0.0, le=1.0)

    def model_post_init(self, __context: Any) -> None:
        del __context
        if not self.variables:
            raise ValueError("algebraic blocks require at least one variable")
        if len(self.variables) != len(set(self.variables)):
            raise ValueError("variables must be unique within an algebraic block")
        if self.family is AlgebraicConstraintFamily.TETRAD:
            if len(self.variables) < 4:
                raise ValueError("tetrad blocks require at least 4 variables")
            if self.expected_rank is not None:
                raise ValueError("expected_rank is only valid for overcomplete blocks")
            if self.max_residual_energy is not None:
                raise ValueError(
                    "max_residual_energy is only valid for overcomplete blocks"
                )
            if self.row_variables or self.col_variables or self.max_rank is not None:
                raise ValueError(
                    "row_variables/col_variables/max_rank are only valid for trek_rank blocks"
                )
            for quadruple in self.quadruples:
                if len(set(quadruple)) != 4:
                    raise ValueError("each tetrad quadruple must contain 4 unique variables")
                if not set(quadruple).issubset(set(self.variables)):
                    raise ValueError(
                        "tetrad quadruples must only reference variables declared in the block"
                    )
            if (
                self.cadmg_scope is not None
                or self.fixing_sequence
                or self.kernel_statement is not None
                or self.identified_kernel_ref is not None
                or self.positivity_required is not None
                or self.model_family is not None
                or self.left_choke_set
                or self.right_choke_set
                or self.invariant_polynomials
                or self.semi_algebraic_inequalities
                or self.derivation_method is not None
                or self.certificate_ref is not None
                or self.precomputed_violation_score is not None
            ):
                raise ValueError(
                    "trek-rank, nested-Verma, and algebraic-geometry fields are not valid for tetrad blocks"
                )
        elif self.family is AlgebraicConstraintFamily.OVERCOMPLETE:
            if self.expected_rank is None:
                raise ValueError("overcomplete blocks require expected_rank")
            if len(self.variables) <= self.expected_rank:
                raise ValueError(
                    "overcomplete blocks require more variables than expected_rank"
                )
            if self.quadruples:
                raise ValueError("quadruples are only valid for tetrad blocks")
            if (
                self.row_variables
                or self.col_variables
                or self.max_rank is not None
                or self.left_choke_set
                or self.right_choke_set
            ):
                raise ValueError(
                    "row_variables/col_variables/max_rank/choke sets are only valid for trek_rank blocks"
                )
            if (
                self.cadmg_scope is not None
                or self.fixing_sequence
                or self.kernel_statement is not None
                or self.identified_kernel_ref is not None
                or self.positivity_required is not None
                or self.model_family is not None
            ):
                raise ValueError(
                    "nested-Verma fields are only valid for nested_verma blocks"
                )
            if (
                self.invariant_polynomials
                or self.semi_algebraic_inequalities
                or self.derivation_method is not None
                or self.certificate_ref is not None
                or self.precomputed_violation_score is not None
            ):
                raise ValueError(
                    "algebraic-geometry fields are only valid for algebraic_geometry_invariant blocks"
                )
        elif self.family is AlgebraicConstraintFamily.TREK_RANK:
            if self.expected_rank is not None:
                raise ValueError("expected_rank is only valid for overcomplete blocks")
            if self.quadruples:
                raise ValueError("quadruples are only valid for tetrad blocks")
            if not self.row_variables or not self.col_variables:
                raise ValueError(
                    "trek_rank blocks require row_variables and col_variables"
                )
            if len(self.row_variables) != len(set(self.row_variables)):
                raise ValueError("row_variables must be unique within a trek_rank block")
            if len(self.col_variables) != len(set(self.col_variables)):
                raise ValueError("col_variables must be unique within a trek_rank block")
            if len(self.left_choke_set) != len(set(self.left_choke_set)):
                raise ValueError("left_choke_set must be unique within a trek_rank block")
            if len(self.right_choke_set) != len(set(self.right_choke_set)):
                raise ValueError("right_choke_set must be unique within a trek_rank block")
            if self.max_rank is None:
                raise ValueError("trek_rank blocks require max_rank")
            if min(len(self.row_variables), len(self.col_variables)) <= self.max_rank:
                raise ValueError(
                    "trek_rank blocks require max_rank to be smaller than the tested submatrix dimension"
                )
            declared = set(self.variables)
            if not (set(self.row_variables) | set(self.col_variables)).issubset(declared):
                raise ValueError(
                    "trek_rank row_variables/col_variables must be included in variables"
                )
            if (
                self.cadmg_scope is not None
                or self.fixing_sequence
                or self.kernel_statement is not None
                or self.identified_kernel_ref is not None
                or self.positivity_required is not None
                or self.model_family is not None
            ):
                raise ValueError(
                    "nested-Verma fields are only valid for nested_verma blocks"
                )
            if (
                self.invariant_polynomials
                or self.semi_algebraic_inequalities
                or self.derivation_method is not None
                or self.certificate_ref is not None
                or self.precomputed_violation_score is not None
            ):
                raise ValueError(
                    "algebraic-geometry fields are only valid for algebraic_geometry_invariant blocks"
                )
        elif self.family is AlgebraicConstraintFamily.NESTED_VERMA:
            if self.quadruples:
                raise ValueError("quadruples are only valid for tetrad blocks")
            if self.expected_rank is not None or self.max_residual_energy is not None:
                raise ValueError(
                    "expected_rank/max_residual_energy are only valid for low-rank covariance blocks"
                )
            if (
                self.row_variables
                or self.col_variables
                or self.max_rank is not None
                or self.left_choke_set
                or self.right_choke_set
            ):
                raise ValueError(
                    "row_variables/col_variables/max_rank/choke sets are only valid for trek_rank blocks"
                )
            if self.cadmg_scope is None:
                raise ValueError("nested_verma blocks require cadmg_scope")
            if not self.fixing_sequence:
                raise ValueError("nested_verma blocks require fixing_sequence")
            if self.kernel_statement is None:
                raise ValueError("nested_verma blocks require kernel_statement")
            if self.model_family is None:
                raise ValueError("nested_verma blocks require model_family")
            if (
                self.invariant_polynomials
                or self.semi_algebraic_inequalities
                or self.derivation_method is not None
                or self.certificate_ref is not None
                or self.precomputed_violation_score is not None
            ):
                raise ValueError(
                    "algebraic-geometry fields are only valid for algebraic_geometry_invariant blocks"
                )
        elif self.family is AlgebraicConstraintFamily.ALGEBRAIC_GEOMETRY_INVARIANT:
            if self.quadruples:
                raise ValueError("quadruples are only valid for tetrad blocks")
            if (
                self.expected_rank is not None
                or self.max_residual_energy is not None
                or self.row_variables
                or self.col_variables
                or self.max_rank is not None
                or self.left_choke_set
                or self.right_choke_set
            ):
                raise ValueError(
                    "low-rank covariance and trek-rank fields are only valid for trek-rank style blocks"
                )
            if (
                self.cadmg_scope is not None
                or self.fixing_sequence
                or self.kernel_statement is not None
                or self.identified_kernel_ref is not None
                or self.positivity_required is not None
                or self.model_family is not None
            ):
                raise ValueError(
                    "nested-Verma fields are only valid for nested_verma blocks"
                )
            if (
                not self.invariant_polynomials
                and not self.semi_algebraic_inequalities
                and self.certificate_ref is None
                and self.derivation_method not in _ALGORITHMIC_ALGEBRAIC_GEOMETRY_METHODS
            ):
                raise ValueError(
                    "algebraic_geometry_invariant blocks require at least one invariant statement or certificate_ref"
                )
        else:
            raise ValueError(
                "AlgebraicBlockSpec only supports explicit ci-adjacent, trek-rank, nested-Verma, and algebraic-geometry block families"
            )


class ImpliedConstraintSpec(BaseModel):
    """Represent one graph-implied constraint and its optional conditioning set."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    constraint_id: str = Field(min_length=1)
    family: AlgebraicConstraintFamily
    statement: str = Field(min_length=1)
    variables: tuple[str, ...]
    conditioning_set: tuple[str, ...] = ()
    source_block_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConstraintEvaluationResult(BaseModel):
    """Store the test outcome for one implied or user-declared algebraic constraint."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    constraint_id: str = Field(min_length=1)
    family: AlgebraicConstraintFamily
    status: Literal["passed", "violated", "skipped", "error", "unsupported"]
    statistic: float | None = None
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    adjusted_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    severity: Literal["info", "warning", "blocker"] = "info"
    assumption_status: AlgebraicAssumptionStatus = AlgebraicAssumptionStatus.UNKNOWN
    regularity_status: AlgebraicRegularityStatus = AlgebraicRegularityStatus.UNKNOWN
    null_distribution: AlgebraicNullDistribution = AlgebraicNullDistribution.UNKNOWN
    calibration_mode: AlgebraicCalibrationMode = AlgebraicCalibrationMode.UNKNOWN
    scope_of_falsification: AlgebraicFalsificationScope = AlgebraicFalsificationScope.UNKNOWN
    ranking_weight: float = Field(default=0.0, ge=0.0)
    reproducibility_tier: AlgebraicReproducibilityTier = AlgebraicReproducibilityTier.UNKNOWN
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AlgebraicConstraintReport(BaseModel):
    """Summarize implied/violated algebraic constraints and suggested graph repairs."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    implied_constraints_ref: ArtifactRefModel | None = None
    violated_constraints_ref: ArtifactRefModel | None = None
    severity: Literal["info", "warning", "blocker"] = "info"
    suggested_repairs: list[str] = Field(default_factory=list)
    families_run: list[AlgebraicConstraintFamily] = Field(default_factory=list)
    n_implied_constraints: int = Field(default=0, ge=0)
    n_violated_constraints: int = Field(default=0, ge=0)
    tested_by_family: dict[str, int] = Field(default_factory=dict)
    violated_by_family: dict[str, int] = Field(default_factory=dict)
    blocker_conditions_met_by_family: dict[str, bool] = Field(default_factory=dict)
    graph_ranking_penalty: float = Field(default=0.0, ge=0.0)
    warnings: list[str] = Field(default_factory=list)
    implied_constraints_preview: list[ImpliedConstraintSpec] = Field(default_factory=list)
    violated_constraints_preview: list[ConstraintEvaluationResult] = Field(default_factory=list)


class LatentTrustLevel(str, Enum):
    """Declare whether a proposed latent structure is research-only, conditional, or validated."""
    RESEARCH = "research"
    CONDITIONAL = "conditional"
    VALIDATED = "validated"


class LatentCausalRole(str, Enum):
    """Classify the causal role claimed for a latent atomic block."""

    CONFOUNDER = "confounder"
    MEDIATOR = "mediator"
    MODERATOR = "moderator"
    UNKNOWN = "unknown"


class LatentBlockStatus(str, Enum):
    """Track whether a latent block is cardinality-identified or only suspected."""

    IDENTIFIED = "identified"
    PARTIAL = "partial"
    SUSPECTED_ONLY = "suspected_only"


class LatentGraphStatus(str, Enum):
    """Describe graph placement support for a latent atomic block."""

    IDENTIFIED = "identified"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class LatentIdentifiabilityStatus(str, Enum):
    """Summarize the theorem-backed identification status of a latent proposal set."""

    FULL = "full"
    PARTIAL = "partial"
    PARTIAL_OR_FULL = "partial_or_full"
    SUSPECTED_ONLY = "suspected_only"


class LatentBlockEvidence(BaseModel):
    """Machine-readable evidence for Stage 9.1 latent cardinality claims."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gin_supported: bool = False
    atomic_structure_supported: bool = False
    shift_localized: bool = False
    minimal_decomposition_supported: bool = False
    role_rule_supported: bool = False
    interaction_signature_supported: bool = False
    pure_child_count: int | None = Field(default=None, ge=0)
    neighbor_count: int | None = Field(default=None, ge=0)
    rank: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LatentBlockProposal(BaseModel):
    """Structured representation of one proposed latent atomic block.

    The public ``LatentDiscoveryBundle`` remains backwards-compatible by keeping
    ``proposed_latent_nodes`` as ``list[str]``. This model defines the canonical
    string and metadata payload used when Stage 9.1 cardinality claims are made.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    latent_id: str = Field(min_length=1)
    block_size: int = Field(ge=1)
    role: LatentCausalRole = LatentCausalRole.UNKNOWN
    candidate_role: LatentCausalRole | None = None
    status: LatentBlockStatus = LatentBlockStatus.PARTIAL
    graph_status: LatentGraphStatus = LatentGraphStatus.UNKNOWN
    within_block_order: str | None = None
    anchor_variables: list[str] = Field(default_factory=list)
    informative_environment_contrasts: list[str] = Field(default_factory=list)
    evidence: LatentBlockEvidence = Field(default_factory=LatentBlockEvidence)
    reason_not_identified: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_identified_claim(self) -> Self:
        if self.status is not LatentBlockStatus.IDENTIFIED:
            return self

        missing_evidence = [
            field
            for field in (
                "gin_supported",
                "atomic_structure_supported",
                "shift_localized",
                "minimal_decomposition_supported",
                "role_rule_supported",
            )
            if not bool(getattr(self.evidence, field))
        ]
        if missing_evidence:
            joined = ", ".join(missing_evidence)
            raise ValueError(f"identified latent block is missing evidence: {joined}")
        if self.role is LatentCausalRole.UNKNOWN:
            raise ValueError("identified latent block requires a non-unknown role")
        if (
            self.role is LatentCausalRole.MODERATOR
            and not self.evidence.interaction_signature_supported
        ):
            raise ValueError(
                "identified moderator block requires interaction_signature_supported"
            )
        return self

    @classmethod
    def from_node_label(cls, value: str) -> Self:
        """Parse the canonical Stage 9.1 node descriptor string."""
        parts = [part.strip() for part in str(value).split("|") if part.strip()]
        if len(parts) < 2:
            raise ValueError("latent node descriptor must include at least one key=value field")

        payload: dict[str, Any] = {"latent_id": parts[0]}
        for part in parts[1:]:
            key, separator, raw_value = part.partition("=")
            if not separator:
                raise ValueError(f"invalid latent node descriptor field: {part!r}")
            payload[key.strip()] = raw_value.strip()
        return cls.model_validate(payload)

    def proposed_node_label(self) -> str:
        """Return the canonical backwards-compatible node descriptor string."""
        if self.status is LatentBlockStatus.SUSPECTED_ONLY:
            raise ValueError(
                "suspected-only latent blocks must stay out of proposed_latent_nodes"
            )

        parts = [
            self.latent_id,
            f"block_size={self.block_size}",
            f"role={self.role.value}",
        ]
        if self.candidate_role is not None:
            parts.append(f"candidate_role={self.candidate_role.value}")
        parts.append(f"status={self.status.value}")
        return "|".join(parts)

    def canonical_identification_conditions(
        self,
        *,
        treatment_variable: str = "T",
        outcome_variable: str = "Y",
    ) -> list[str]:
        """Emit canonical Stage 9.1 machine-checkable identification conditions."""
        latent_id = self.latent_id
        block_size = self.block_size
        rank = self.evidence.rank or block_size
        pure_child_threshold = 2 * block_size
        neighbor_threshold = 2 * block_size + 1
        conditions = [
            "class:multi_env_linear_nongaussian_latent_sem",
            (
                f"atomic_block:{latent_id}:p={block_size}:"
                f"pure_children>={pure_child_threshold}:"
                f"neighbors>={neighbor_threshold}:rank={rank}"
            ),
            (
                f"minimality:{latent_id}:"
                f"minimal_explanation_across_environments="
                f"{str(self.evidence.minimal_decomposition_supported).lower()}"
            ),
        ]
        if self.informative_environment_contrasts:
            for contrast in self.informative_environment_contrasts:
                conditions.append(
                    f"env_shift:{latent_id}:contrast={contrast}:"
                    f"localized={str(self.evidence.shift_localized).lower()}"
                )
        else:
            conditions.append(
                f"env_shift:{latent_id}:localized="
                f"{str(self.evidence.shift_localized).lower()}"
            )

        if self.role is LatentCausalRole.CONFOUNDER:
            conditions.append(
                f"role_rule:{latent_id}:"
                f"ancestor({treatment_variable})&ancestor({outcome_variable})"
                f"&!descendant({treatment_variable})"
            )
        elif self.role is LatentCausalRole.MEDIATOR:
            conditions.append(
                f"role_rule:{latent_id}:"
                f"descendant({treatment_variable})&ancestor({outcome_variable})"
            )
        elif self.role is LatentCausalRole.MODERATOR:
            if self.evidence.interaction_signature_supported:
                conditions.append(
                    f"moderator_extension:{latent_id}:interaction_signature=verified"
                )
            else:
                conditions.append(
                    f"moderator_extension:{latent_id}:"
                    "failed_no_identified_interaction_signature"
                )
        elif self.candidate_role is LatentCausalRole.MODERATOR:
            conditions.append(
                f"moderator_extension:{latent_id}:"
                "failed_no_identified_interaction_signature"
            )

        return _dedupe_text(conditions)


class LatentCardinalityIdentificationSpec(BaseModel):
    """Stage 9.1 theorem-backed latent-cardinality integration payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_class: Literal["ME-LiNGLaH-S", "ME-LiNGLaH-S-Int"] = "ME-LiNGLaH-S"
    identifiability_status: LatentIdentifiabilityStatus = LatentIdentifiabilityStatus.PARTIAL
    latent_blocks: list[LatentBlockProposal] = Field(default_factory=list)
    latent_candidates: list[dict[str, Any]] = Field(default_factory=list)
    ambiguity_notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_block_layout(self) -> Self:
        if any(block.status is LatentBlockStatus.SUSPECTED_ONLY for block in self.latent_blocks):
            raise ValueError(
                "suspected-only latent blocks must be stored in latent_candidates, not latent_blocks"
            )
        if (
            self.model_class != "ME-LiNGLaH-S-Int"
            and any(
                block.status is LatentBlockStatus.IDENTIFIED
                and block.role is LatentCausalRole.MODERATOR
                for block in self.latent_blocks
            )
        ):
            raise ValueError(
                "identified moderator blocks require the ME-LiNGLaH-S-Int model class"
            )
        return self

    @classmethod
    def from_bundle_metadata(cls, metadata: Mapping[str, Any] | None) -> Self | None:
        """Recover a Stage 9.1 spec from bundle metadata when present."""
        if not isinstance(metadata, Mapping):
            return None

        keys = {
            "model_class",
            "identifiability_status",
            "latent_blocks",
            "latent_candidates",
            "ambiguity_notes",
        }
        if not any(key in metadata for key in keys):
            return None

        extra_metadata = {
            str(key): value for key, value in metadata.items() if str(key) not in keys
        }
        return cls.model_validate(
            {
                "model_class": metadata.get("model_class", "ME-LiNGLaH-S"),
                "identifiability_status": metadata.get(
                    "identifiability_status",
                    LatentIdentifiabilityStatus.PARTIAL.value,
                ),
                "latent_blocks": list(metadata.get("latent_blocks", []) or []),
                "latent_candidates": list(metadata.get("latent_candidates", []) or []),
                "ambiguity_notes": list(metadata.get("ambiguity_notes", []) or []),
                "metadata": extra_metadata,
            }
        )

    @classmethod
    def from_bundle(cls, bundle: LatentDiscoveryBundle | None) -> Self | None:
        """Recover a Stage 9.1 spec from a latent discovery bundle."""
        if bundle is None:
            return None
        return cls.from_bundle_metadata(bundle.metadata)

    def proposed_latent_nodes(self) -> list[str]:
        """Return canonical proposed latent node strings for cardinality-backed blocks."""
        return [
            block.proposed_node_label()
            for block in self.latent_blocks
            if block.status is not LatentBlockStatus.SUSPECTED_ONLY
        ]

    def canonical_identification_conditions(
        self,
        *,
        treatment_variable: str = "T",
        outcome_variable: str = "Y",
    ) -> list[str]:
        """Return canonical conditions for all structured latent block proposals."""
        conditions = ["class:multi_env_linear_nongaussian_latent_sem"]
        for block in self.latent_blocks:
            if block.status is LatentBlockStatus.SUSPECTED_ONLY:
                continue
            conditions.extend(
                block.canonical_identification_conditions(
                    treatment_variable=treatment_variable,
                    outcome_variable=outcome_variable,
                )
            )
        return _dedupe_text(conditions)

    def bundle_metadata(self) -> dict[str, Any]:
        """Return the backwards-compatible metadata payload for LatentDiscoveryBundle."""
        payload: dict[str, Any] = dict(self.metadata)
        payload.update(
            {
                "model_class": self.model_class,
                "identifiability_status": self.identifiability_status.value,
                "latent_blocks": [
                    block.model_dump(mode="json") for block in self.latent_blocks
                ],
            }
        )
        if self.latent_candidates:
            payload["latent_candidates"] = list(self.latent_candidates)
        if self.ambiguity_notes:
            payload["ambiguity_notes"] = list(self.ambiguity_notes)
        return payload

    def to_bundle(
        self,
        *,
        inducing_environments: list[str],
        falsification_tests: list[str],
        assumption_cards: list["LatentAssumptionCard"] | None = None,
        trust_level: LatentTrustLevel = LatentTrustLevel.RESEARCH,
        no_promotion_reasons: list[str] | None = None,
        metadata: Mapping[str, Any] | None = None,
        treatment_variable: str = "T",
        outcome_variable: str = "Y",
    ) -> "LatentDiscoveryBundle":
        """Materialize the Stage 9.1 spec as a proof-only latent discovery bundle."""
        bundle_metadata = self.bundle_metadata()
        if isinstance(metadata, Mapping):
            bundle_metadata.update(dict(metadata))
        reasons = _dedupe_text(
            [
                *(list(no_promotion_reasons) if no_promotion_reasons is not None else []),
                "latent_discovery_proof_only",
            ]
        )
        return LatentDiscoveryBundle(
            proposed_latent_nodes=self.proposed_latent_nodes(),
            inducing_environments=list(inducing_environments),
            identification_conditions=self.canonical_identification_conditions(
                treatment_variable=treatment_variable,
                outcome_variable=outcome_variable,
            ),
            falsification_tests=list(falsification_tests),
            trust_level=trust_level,
            assumption_cards=list(assumption_cards or []),
            readiness_cap="proof_only",
            human_gate_required=True,
            promotion_allowed=False,
            no_promotion_reasons=reasons,
            not_for_decision_support=True,
            metadata=bundle_metadata,
        )


class LatentAssumptionCard(BaseModel):
    """Document one latent-variable assumption and its falsification hook."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    assumption_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    evidence_basis: list[str] = Field(default_factory=list)
    falsification_hook: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LatentCardinalityEvidencePayload(BaseModel):
    """Typed Stage 9.1 producer evidence stored in bundle metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_class: Literal["ME-LiNGLaH-S", "ME-LiNGLaH-S-Int"] = "ME-LiNGLaH-S"
    treatment_variable: str = Field(default="T", min_length=1)
    outcome_variable: str = Field(default="Y", min_length=1)
    inducing_environments: list[str] = Field(default_factory=list)
    falsification_tests: list[str] = Field(default_factory=list)
    assumption_cards: list[LatentAssumptionCard] = Field(default_factory=list)
    latent_blocks: list[LatentBlockProposal] = Field(default_factory=list)
    latent_candidates: list[dict[str, Any]] = Field(default_factory=list)
    ambiguity_notes: list[str] = Field(default_factory=list)
    prerequisites_missing: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_metadata(cls, metadata: Mapping[str, Any] | None) -> Self | None:
        """Recover the typed Stage 9.1 evidence payload from bundle metadata."""

        if not isinstance(metadata, Mapping):
            return None
        payload = metadata.get(LATENT_CARDINALITY_EVIDENCE_KEY)
        if not isinstance(payload, Mapping):
            return None
        return cls.model_validate(payload)


class LatentPromotionEvidence(BaseModel):
    """Stage 9.3 structured evidence supporting a LatentDiscoveryBundle promotion.

    The bundle itself remains a research artifact; promotion above ``proof_only``
    is judge-derived from this evidence block and never self-certified by the
    frontier module. Populated refs are pointers to replayable artifacts
    (tests, audits, benchmark traces, reviewer decisions).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    observable_implication_refs: list[ArtifactRefModel] = Field(default_factory=list)
    local_misspecification_test_refs: list[ArtifactRefModel] = Field(default_factory=list)
    environment_stability_ref: ArtifactRefModel | None = None
    rival_explanation_audit_ref: ArtifactRefModel | None = None
    external_evidence_refs: list[ArtifactRefModel] = Field(default_factory=list)
    replication_refs: list[ArtifactRefModel] = Field(default_factory=list)
    hidden_benchmark_ref: ArtifactRefModel | None = None
    reviewer_decision_ref: ArtifactRefModel | None = None
    exclusion_test_refs: list[ArtifactRefModel] = Field(default_factory=list)
    external_anchor_refs: list[ArtifactRefModel] = Field(default_factory=list)
    cross_model_robustness_refs: list[ArtifactRefModel] = Field(default_factory=list)
    scope_regime: list[str] = Field(default_factory=list)
    invariance_level: Literal[
        "none", "configural", "metric", "scalar", "strict", "approximate"
    ] = "none"
    measurement_scope: bool = False
    structural_interpretation_rejected: bool = False
    notes: list[str] = Field(default_factory=list)


class LatentPromotionVerdict(BaseModel):
    """Machine-readable Stage 9.3 promotion verdict over a latent bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_trust_level: LatentTrustLevel
    derived_trust_level: LatentTrustLevel
    derived_readiness_cap: Literal["proof_only", "bounds_ready", "estimation_ready"]
    claim_mode: Literal["proof_only", "bounded_latent", "validated_measurement_latent"]
    degradation_mode: Literal["research_only", "bounds_only", "measurement_ready"]
    promotion_allowed: bool = False
    not_for_decision_support: bool = True
    human_gate_required: bool = True
    passed_gates: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence_refs: list[ArtifactRefModel] = Field(default_factory=list)
    scope_regime: list[str] = Field(default_factory=list)


class LatentDiscoveryBundle(BaseModel):
    """Disclose proposed latent nodes, test hooks, and promotion limits."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    proposed_latent_nodes: list[str] = Field(default_factory=list)
    inducing_environments: list[str] = Field(default_factory=list)
    identification_conditions: list[str] = Field(default_factory=list)
    falsification_tests: list[str] = Field(default_factory=list)
    trust_level: LatentTrustLevel = LatentTrustLevel.RESEARCH
    assumption_cards: list[LatentAssumptionCard] = Field(default_factory=list)
    readiness_cap: Literal["proof_only", "bounds_ready", "estimation_ready"] = "proof_only"
    human_gate_required: bool = True
    promotion_allowed: bool = False
    no_promotion_reasons: list[str] = Field(default_factory=list)
    not_for_decision_support: bool = True
    promotion_evidence: LatentPromotionEvidence | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def latent_cardinality_spec(self) -> LatentCardinalityIdentificationSpec | None:
        """Return the Stage 9.1 cardinality spec when this bundle carries one."""
        return LatentCardinalityIdentificationSpec.from_bundle(self)


def _dedupe_text(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


class CausalDiscoveryReport(BaseModel):
    """Output of a causal-discovery run, including optional latent diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    method: str
    graph: CausalGraphModel
    resolved_graph: CausalGraphModel | None = None
    bootstrap_stability: dict[str, float] = Field(default_factory=dict)
    n_bootstrap: int = Field(default=0, ge=0)
    significance_level: float = Field(default=0.05, ge=0.0, le=1.0)
    computation_time_seconds: float = Field(default=0.0, ge=0.0)
    warnings: list[str] = Field(default_factory=list)
    algebraic_constraints: AlgebraicConstraintReport | None = None
    latent_discovery: LatentDiscoveryBundle | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataType(str, Enum):
    """Classify whether discovery inputs are cross-sectional or time-series."""
    CROSS_SECTIONAL = "cross_sectional"
    TIME_SERIES = "time_series"


class DimensionRegime(str, Enum):
    """Bucket discovery inputs by variable-count regime for algorithm selection."""
    LOW_DIM = "low_dim"   # n_vars <= 20
    MED_DIM = "med_dim"   # 21 <= n_vars <= 50
    HIGH_DIM = "high_dim"  # n_vars > 50


class DataCharacteristics(BaseModel):
    """Summarize discovery dataset shape, stationarity, and latent-confounding risk."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    data_type: DataType
    n_samples: int
    n_variables: int
    dimension_regime: DimensionRegime
    estimated_density: float
    has_mixed_types: bool
    suspected_latent_confounders: bool
    is_stationary: bool | None = None
    max_lag: int | None = None


class EdgeAgreement(BaseModel):
    """Summarize bootstrap or multi-algorithm agreement for one candidate edge."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    edge_key: str
    presence_score: float
    orientation_confidence: float
    mark_src: str
    mark_dst: str
    contributing_algorithms: list[str]


class DiscoveryPipelineReport(BaseModel):
    """Aggregate discovery results, consensus PAG output, and algorithm agreement metrics."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    unified_pag: CausalGraphModel
    individual_results: list[CausalDiscoveryReport]
    algorithm_weights: dict[str, float]
    edge_agreements: list[EdgeAgreement]
    skeleton_agreement: dict[str, float] = Field(default_factory=dict)
    temporal_dag: CausalGraphModel | None = None
    regime_shift_certificate: RegimeShiftIdentificationCertificate | None = None
    pag_validity_violations: list[str] = Field(default_factory=list)
    data_characteristics: DataCharacteristics
    n_algorithms_run: int
    warnings: list[str] = Field(default_factory=list)
    computation_time_seconds: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


def persist_causal_discovery_report(
    store: ArtifactStore,
    report: CausalDiscoveryReport,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.causal_discovery_report",
    schema_version: str = "1.0",
) -> CausalDiscoveryReportRef:
    """Persist a discovery report and materialize large constraint payloads when needed."""
    persisted_report = _materialize_algebraic_constraint_payloads(
        store,
        report,
        inputs=inputs,
    )
    ref = put_json_artifact(
        store,
        persisted_report.model_dump(mode="json"),
        kind="ir.causal_discovery_report",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CausalDiscoveryReportRef.model_validate(ref)


def load_causal_discovery_report(
    store: ArtifactStore,
    ref: CausalDiscoveryReportRef,
) -> CausalDiscoveryReport:
    """Load causal discovery report."""
    payload = get_json_artifact(store, ref.artifact_id)
    report = CausalDiscoveryReport.model_validate(payload)
    return _hydrate_algebraic_constraint_payloads(store, report)


def _materialize_algebraic_constraint_payloads(
    store: ArtifactStore,
    report: CausalDiscoveryReport,
    *,
    inputs: list[InputRef] | None,
) -> CausalDiscoveryReport:
    algebraic = report.algebraic_constraints
    if algebraic is None:
        return report

    updated = algebraic
    if algebraic.implied_constraints_ref is None and algebraic.implied_constraints_preview:
        ref = put_json_artifact(
            store,
            [item.model_dump(mode="json") for item in algebraic.implied_constraints_preview],
            kind=_ALGEBRAIC_IMPLIED_CONSTRAINTS_KIND,
            schema_name=_ALGEBRAIC_IMPLIED_CONSTRAINTS_SCHEMA_NAME,
            schema_version="1.0",
            inputs=inputs,
            canon_spec=CanonSpec(forbid_floats=False),
        )
        updated = updated.model_copy(
            update={
                "implied_constraints_ref": ArtifactRefModel.model_validate(ref),
                "implied_constraints_preview": [],
            }
        )

    if updated.violated_constraints_ref is None and updated.violated_constraints_preview:
        ref = put_json_artifact(
            store,
            [item.model_dump(mode="json") for item in updated.violated_constraints_preview],
            kind=_ALGEBRAIC_VIOLATED_CONSTRAINTS_KIND,
            schema_name=_ALGEBRAIC_VIOLATED_CONSTRAINTS_SCHEMA_NAME,
            schema_version="1.0",
            inputs=inputs,
            canon_spec=CanonSpec(forbid_floats=False),
        )
        updated = updated.model_copy(
            update={
                "violated_constraints_ref": ArtifactRefModel.model_validate(ref),
                "violated_constraints_preview": [],
            }
        )

    if updated == algebraic:
        return report
    return report.model_copy(update={"algebraic_constraints": updated})


def _hydrate_algebraic_constraint_payloads(
    store: ArtifactStore,
    report: CausalDiscoveryReport,
) -> CausalDiscoveryReport:
    algebraic = report.algebraic_constraints
    if algebraic is None:
        return report

    updates: dict[str, Any] = {}
    if algebraic.implied_constraints_ref is not None and not algebraic.implied_constraints_preview:
        payload = get_json_artifact(store, algebraic.implied_constraints_ref.artifact_id)
        updates["implied_constraints_preview"] = [
            ImpliedConstraintSpec.model_validate(item) for item in payload
        ]

    if algebraic.violated_constraints_ref is not None and not algebraic.violated_constraints_preview:
        payload = get_json_artifact(store, algebraic.violated_constraints_ref.artifact_id)
        updates["violated_constraints_preview"] = [
            ConstraintEvaluationResult.model_validate(item) for item in payload
        ]

    if not updates:
        return report
    return report.model_copy(
        update={"algebraic_constraints": algebraic.model_copy(update=updates)}
    )


__all__ = [
    "AlgebraicAssumptionRegime",
    "AlgebraicAssumptionStatus",
    "AlgebraicBlockSpec",
    "AlgebraicCalibrationMode",
    "AlgebraicConstraintFamily",
    "AlgebraicConstraintReport",
    "AlgebraicFalsificationScope",
    "AlgebraicNullDistribution",
    "AlgebraicRegularityStatus",
    "AlgebraicReproducibilityTier",
    "AlgebraicTestMode",
    "CausalDiscoveryReport",
    "ConstraintEvaluationResult",
    "DataType",
    "DimensionRegime",
    "DataCharacteristics",
    "EdgeAgreement",
    "ImpliedConstraintSpec",
    "DiscoveryPipelineReport",
    "persist_causal_discovery_report",
    "LatentAssumptionCard",
    "LatentBlockEvidence",
    "LatentBlockProposal",
    "LatentBlockStatus",
    "LatentCardinalityIdentificationSpec",
    "LatentCardinalityEvidencePayload",
    "LatentCausalRole",
    "LatentDiscoveryBundle",
    "LatentGraphStatus",
    "LatentIdentifiabilityStatus",
    "LATENT_CARDINALITY_EVIDENCE_KEY",
    "LATENT_CARDINALITY_FAILURE_REASONS_KEY",
    "LatentPromotionEvidence",
    "LatentPromotionVerdict",
    "LatentTrustLevel",
    "NestedMarkovModelFamily",
    "load_causal_discovery_report",
]
