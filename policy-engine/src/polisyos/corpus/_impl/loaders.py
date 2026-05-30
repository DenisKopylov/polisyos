"""Load W11.D universal outcome corpus fixtures.

The loader is an internal evaluation consumer. It reads repo-owned fixture
artifacts and enforces split and rotation policy; it does not compile policy
intent, mint claim authority, or turn fixture expectations into runtime truth.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from .annotations import PolicyCaseAnnotation

UNIVERSAL_CORPUS_FIXTURE_SCHEMA_VERSION = "policyos.universal_corpus_fixture.v1"
UNIVERSAL_CORPUS_MANIFEST_SCHEMA_VERSION = "policyos.universal_corpus_manifest.v1"

AuthorityLevel = Literal["research", "governed", "production"]
RequirementFamily = Literal["data", "legal", "method", "participation", "scholar"]
AdapterBindingStatus = Literal["selected", "rejected", "blocked"]
CloseoutState = Literal["publishable", "limited", "contested", "blocked", "review_required"]
ProjectionTruthfulness = Literal[
    "faithful",
    "limitation_required",
    "contested",
    "unfaithful",
]

_REQUIRED_REQUIREMENT_FAMILIES: frozenset[str] = frozenset(
    {"data", "legal", "method", "participation", "scholar"}
)
_REQUIRED_BINDING_STATUSES: frozenset[str] = frozenset({"selected", "rejected", "blocked"})
_REQUIRED_AUTHORITY_LEVELS: frozenset[str] = frozenset(
    {"research", "governed", "production"}
)


class UniversalCorpusFixtureError(ValueError):
    """Raised when a universal corpus fixture pack is internally inconsistent."""


class FixtureRotationError(UniversalCorpusFixtureError):
    """Raised when rotating fixtures violate W11.D rotation policy."""


class HiddenFixtureAccessError(UniversalCorpusFixtureError):
    """Raised when hidden fixtures are selected without explicit opt-in."""


class UniversalCorpusSplit(StrEnum):
    """Fixture split labels used to avoid evaluator overfitting."""

    PUBLIC = "public"
    HIDDEN = "hidden"
    ROTATING = "rotating"


class _StrictCorpusModel(BaseModel):
    """Shared strict Pydantic base for W11.D fixture models."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class PolicyIntentFixture(_StrictCorpusModel):
    """Input policy intent captured by one universal corpus fixture."""

    intent_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=1)
    policy_time: str = Field(min_length=1)
    authority_levels: tuple[AuthorityLevel, ...] = Field(min_length=1)
    instrument_type: str = Field(min_length=1)
    target_population: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "intent_id",
        "text",
        "jurisdiction",
        "policy_time",
        "instrument_type",
        "target_population",
        mode="before",
    )
    @classmethod
    def _clean_text(cls, value: object) -> str:
        return _required_text(value)

    @field_validator("authority_levels", mode="before")
    @classmethod
    def _clean_authority_levels(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class ClaimAnnotation(_StrictCorpusModel):
    """W11.B claim/evidence decomposition row."""

    claim_id: str = Field(min_length=1)
    claim_family: str = Field(min_length=1)
    text_ref: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    method_refs: tuple[str, ...] = Field(default=())
    legal_refs: tuple[str, ...] = Field(default=())
    participation_refs: tuple[str, ...] = Field(default=())
    risks: tuple[str, ...] = Field(default=())
    tradeoffs: tuple[str, ...] = Field(default=())
    admissibility_label: str = Field(min_length=1)
    limitation_refs: tuple[str, ...] = Field(default=())
    contestability_status: str = Field(min_length=1)

    @field_validator(
        "claim_id",
        "claim_family",
        "text_ref",
        "admissibility_label",
        "contestability_status",
        mode="before",
    )
    @classmethod
    def _clean_required_text(cls, value: object) -> str:
        return _required_text(value)

    @field_validator(
        "evidence_refs",
        "method_refs",
        "legal_refs",
        "participation_refs",
        "risks",
        "tradeoffs",
        "limitation_refs",
        mode="before",
    )
    @classmethod
    def _clean_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class ObligationAnnotation(_StrictCorpusModel):
    """W11.B annotated obligation expected from universal compilation."""

    obligation_id: str = Field(min_length=1)
    generated_from_facets: tuple[str, ...] = Field(min_length=1)
    required_evidence_family: str = Field(min_length=1)
    status: str = Field(min_length=1)
    reviewer_notes: str | None = None

    @field_validator("obligation_id", "required_evidence_family", "status", mode="before")
    @classmethod
    def _clean_required_text(cls, value: object) -> str:
        return _required_text(value)

    @field_validator("reviewer_notes", mode="before")
    @classmethod
    def _clean_optional_text(cls, value: object) -> str | None:
        return _optional_text(value)

    @field_validator("generated_from_facets", mode="before")
    @classmethod
    def _clean_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class ClaimEvidenceAnnotations(_StrictCorpusModel):
    """Per-case W11.B decomposition annotations consumed by W11.D fixtures."""

    annotation_ref: str = Field(min_length=1)
    claims: tuple[ClaimAnnotation, ...] = Field(min_length=1)
    obligations: tuple[ObligationAnnotation, ...] = Field(min_length=1)


class ExpertClaimLabel(_StrictCorpusModel):
    """W11.C expert label for one claim and rubric dimension."""

    claim_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    dimension_id: str = Field(min_length=1)
    status_should_have_been: str = Field(min_length=1)
    failure_mode: str | None = None
    why_structural_checks_missed_it: str | None = None
    required_surface_change: str | None = None


class ExpertAdjudicationLabels(_StrictCorpusModel):
    """W11.C expert adjudication labels attached to one case."""

    case_label: Literal[
        "semantic_pass",
        "limitation_required",
        "contested",
        "unsupported",
        "false_pass",
        "fabricated_unverifiable",
        "reviewer_disagreement",
    ]
    claim_labels: tuple[ExpertClaimLabel, ...] = Field(min_length=1)
    reviewer_topology_ref: str = Field(min_length=1)


class FacetExpectation(_StrictCorpusModel):
    """Expected W6.A facet output for a fixture case."""

    facet_name: str = Field(min_length=1)
    expected_value: str = Field(min_length=1)
    concept_ref: str = Field(min_length=1)
    authority_profile_ref: str | None = None
    time_ref: str | None = None


class ExpectedFacetOutputs(_StrictCorpusModel):
    """Expected facet outputs for one case."""

    facets: tuple[FacetExpectation, ...] = Field(min_length=1)


class ObligationFrontierExpectation(_StrictCorpusModel):
    """Expected W6.C obligation graph frontier slice."""

    obligation_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    priority: str = Field(min_length=1)
    source_class: str = Field(min_length=1)
    claim_refs: tuple[str, ...] = Field(min_length=1)

    @field_validator("claim_refs", mode="before")
    @classmethod
    def _clean_refs(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class ExpectedObligationGraphSlice(_StrictCorpusModel):
    """Expected obligation graph slice for fixture comparison."""

    frontier: tuple[ObligationFrontierExpectation, ...] = Field(min_length=1)


class ClaimFamilyExpectation(_StrictCorpusModel):
    """Expected claim-family assignment for one claim."""

    claim_id: str = Field(min_length=1)
    claim_family: str = Field(min_length=1)
    expected_support_status: str = Field(min_length=1)


class ExpectedClaimFamilies(_StrictCorpusModel):
    """Expected claim family assignments for one case."""

    families: tuple[ClaimFamilyExpectation, ...] = Field(min_length=1)


class ExpectedRequirementSpecs(_StrictCorpusModel):
    """Expected W7 RequirementSpec slices grouped by producer family."""

    families: dict[RequirementFamily, tuple[dict[str, Any], ...]]

    @model_validator(mode="after")
    def _validate_requirement_families(self) -> ExpectedRequirementSpecs:
        found = set(self.families)
        if found != _REQUIRED_REQUIREMENT_FAMILIES:
            missing = sorted(_REQUIRED_REQUIREMENT_FAMILIES - found)
            extra = sorted(found - _REQUIRED_REQUIREMENT_FAMILIES)
            raise ValueError(
                "expected_requirement_specs_family_mismatch: "
                f"missing={missing} extra={extra}"
            )
        for family, specs in self.families.items():
            if not specs:
                raise ValueError(f"expected_requirement_specs_empty_family:{family}")
            for spec in specs:
                if not _optional_text(spec.get("requirement_id")):
                    raise ValueError(
                        f"expected_requirement_spec_missing_requirement_id:{family}"
                    )
        return self


class AdapterBindingExpectation(_StrictCorpusModel):
    """Expected selected, rejected, or blocked producer-adapter binding."""

    binding_id: str = Field(min_length=1)
    adapter: str = Field(min_length=1)
    status: AdapterBindingStatus
    requirement_id: str = Field(min_length=1)
    reason_code: str = Field(min_length=1)
    binding_ref: str | None = None


class ExpectedAdapterBindings(_StrictCorpusModel):
    """Expected W7 adapter binding outcomes for one case."""

    bindings: tuple[AdapterBindingExpectation, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_binding_status_coverage(self) -> ExpectedAdapterBindings:
        statuses = {binding.status for binding in self.bindings}
        if statuses < _REQUIRED_BINDING_STATUSES:
            missing = sorted(_REQUIRED_BINDING_STATUSES - statuses)
            raise ValueError(f"expected_adapter_binding_status_missing:{missing}")
        return self


class CloseoutStateExpectation(_StrictCorpusModel):
    """Expected closeout state for one authority level."""

    authority_level: AuthorityLevel
    state: CloseoutState
    required_surface_refs: tuple[str, ...] = Field(min_length=1)
    blocker_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())

    @field_validator("required_surface_refs", "blocker_refs", "limitation_refs", mode="before")
    @classmethod
    def _clean_refs(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class ExpectedCloseoutStates(_StrictCorpusModel):
    """Expected closeout states across research, governed, and production authority."""

    states: tuple[CloseoutStateExpectation, ...] = Field(min_length=3)

    @model_validator(mode="after")
    def _validate_authority_coverage(self) -> ExpectedCloseoutStates:
        found = {state.authority_level for state in self.states}
        if found != _REQUIRED_AUTHORITY_LEVELS:
            raise ValueError(f"expected_closeout_authority_levels_mismatch:{sorted(found)}")
        return self


class ProjectionTruthfulnessExpectation(_StrictCorpusModel):
    """Expected projection truthfulness for one audience surface."""

    audience: str = Field(min_length=1)
    truthfulness: ProjectionTruthfulness
    must_disclose_refs: tuple[str, ...] = Field(default=())
    may_not_claim: tuple[str, ...] = Field(default=())

    @field_validator("must_disclose_refs", "may_not_claim", mode="before")
    @classmethod
    def _clean_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class ExpectedProjectionTruthfulness(_StrictCorpusModel):
    """Expected projection truthfulness surface for one case."""

    projections: tuple[ProjectionTruthfulnessExpectation, ...] = Field(min_length=1)


class UniversalCorpusFixture(_StrictCorpusModel):
    """Machine-loadable W11.D per-case fixture."""

    schema_version: Literal["policyos.universal_corpus_fixture.v1"] = (
        UNIVERSAL_CORPUS_FIXTURE_SCHEMA_VERSION
    )
    case_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    split: UniversalCorpusSplit
    source_case_ref: str | None = None
    redacted_source_hash: str | None = None
    compilation_intent_text: str | None = None
    concept_spine_refs: dict[str, Any] = Field(default_factory=dict)
    compilation_inputs: dict[str, Any] = Field(default_factory=dict)
    producer_pipeline: dict[str, Any] = Field(default_factory=dict)
    critic_ensemble: dict[str, Any] = Field(default_factory=dict)
    input_intent_ref: str = Field(min_length=1)
    intent: PolicyIntentFixture
    claim_evidence_annotations: PolicyCaseAnnotation | ClaimEvidenceAnnotations
    expert_adjudication: ExpertAdjudicationLabels
    expected_facets: ExpectedFacetOutputs
    expected_obligation_graph: ExpectedObligationGraphSlice
    expected_claim_families: ExpectedClaimFamilies
    expected_requirement_specs: ExpectedRequirementSpecs
    expected_adapter_bindings: ExpectedAdapterBindings
    expected_closeout_states: ExpectedCloseoutStates
    expected_projection_truthfulness: ExpectedProjectionTruthfulness
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_fixture_chain(self) -> UniversalCorpusFixture:
        if self.input_intent_ref != self.intent.intent_id:
            raise ValueError("input_intent_ref must match intent.intent_id")
        if not (self.source_case_ref or self.redacted_source_hash):
            raise ValueError("source_case_ref_or_redacted_source_hash_required")
        if self.redacted_source_hash and not self.redacted_source_hash.startswith("sha256:"):
            raise ValueError("redacted_source_hash must use sha256:<hex> form")
        if (
            isinstance(self.claim_evidence_annotations, PolicyCaseAnnotation)
            and self.claim_evidence_annotations.case_id != self.case_id
        ):
            raise ValueError("claim_evidence_annotation_case_id_mismatch")
        claim_ids = {claim.claim_id for claim in self.claim_evidence_annotations.claims}
        expected_claim_ids = {
            family.claim_id for family in self.expected_claim_families.families
        }
        if not expected_claim_ids <= claim_ids:
            raise ValueError("expected_claim_families_reference_unknown_claim")
        return self


class FixtureManifestEntry(_StrictCorpusModel):
    """Manifest row pointing to one per-case fixture file."""

    case_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    split: UniversalCorpusSplit
    domain: str = Field(min_length=1)
    authority_levels: tuple[AuthorityLevel, ...] = Field(min_length=1)
    rotation_group: str | None = None

    @field_validator("path", mode="before")
    @classmethod
    def _validate_relative_path(cls, value: object) -> str:
        text = _required_text(value)
        path = Path(text)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("fixture manifest paths must be repo-root relative")
        return text

    @field_validator("authority_levels", mode="before")
    @classmethod
    def _clean_authority_levels(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class RotationRound(_StrictCorpusModel):
    """One evaluation round's rotating fixture selection."""

    round_id: str = Field(min_length=1)
    started_at: AwareDatetime
    rotating_case_ids: tuple[str, ...] = Field(default=())

    @field_validator("rotating_case_ids", mode="before")
    @classmethod
    def _clean_ids(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class RotationAcknowledgement(_StrictCorpusModel):
    """Durable acknowledgement allowing a consecutive rotating fixture reuse."""

    case_id: str = Field(min_length=1)
    round_id: str = Field(min_length=1)
    ack_ref: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class RotationPolicy(_StrictCorpusModel):
    """W11.D rotation policy preventing hidden-answer overfitting."""

    policy_id: str = Field(min_length=1)
    active_round_id: str = Field(min_length=1)
    previous_round_id: str | None = None
    min_rotation_days: int = Field(ge=1)
    no_consecutive_round_reuse: bool = True
    rounds: tuple[RotationRound, ...] = Field(default=())
    acknowledgements: tuple[RotationAcknowledgement, ...] = Field(default=())
    consecutive_reuse_case_ids: tuple[str, ...] = Field(default=())

    @model_validator(mode="after")
    def _derive_consecutive_reuse(self) -> RotationPolicy:
        rounds = {round_.round_id: round_ for round_ in self.rounds}
        active = rounds.get(self.active_round_id)
        previous = rounds.get(self.previous_round_id or "")
        if active is None:
            object.__setattr__(self, "consecutive_reuse_case_ids", ())
            return self
        if self.previous_round_id and previous is None:
            raise ValueError("rotation_previous_round_missing")
        overlap = ()
        if previous is not None:
            overlap = tuple(
                sorted(set(previous.rotating_case_ids) & set(active.rotating_case_ids))
            )
        object.__setattr__(self, "consecutive_reuse_case_ids", overlap)
        return self

    def missing_consecutive_reuse_ack_case_ids(self) -> tuple[str, ...]:
        """Return reused rotating cases lacking an acknowledgement for active round."""

        if not self.no_consecutive_round_reuse:
            return ()
        acknowledged = {
            acknowledgement.case_id
            for acknowledgement in self.acknowledgements
            if acknowledgement.round_id == self.active_round_id
        }
        return tuple(
            case_id
            for case_id in self.consecutive_reuse_case_ids
            if case_id not in acknowledged
        )

    def active_rotating_case_ids(self) -> tuple[str, ...]:
        """Return rotating case ids for the active evaluation round."""

        for round_ in self.rounds:
            if round_.round_id == self.active_round_id:
                return round_.rotating_case_ids
        return ()


class UniversalCorpusManifest(_StrictCorpusModel):
    """Manifest for a W11.D universal corpus fixture pack."""

    schema_version: Literal["policyos.universal_corpus_manifest.v1"] = (
        UNIVERSAL_CORPUS_MANIFEST_SCHEMA_VERSION
    )
    fixture_schema_version: Literal["policyos.universal_corpus_fixture.v1"] = (
        UNIVERSAL_CORPUS_FIXTURE_SCHEMA_VERSION
    )
    generated_at: AwareDatetime
    source_plan_ref: str = Field(min_length=1)
    fixtures: tuple[FixtureManifestEntry, ...]
    rotation_policy: RotationPolicy

    @model_validator(mode="after")
    def _validate_manifest_index(self) -> UniversalCorpusManifest:
        case_ids = [entry.case_id for entry in self.fixtures]
        duplicate_ids = sorted({case_id for case_id in case_ids if case_ids.count(case_id) > 1})
        if duplicate_ids:
            raise ValueError(f"universal_corpus_duplicate_case_ids:{duplicate_ids}")
        by_id = {entry.case_id: entry for entry in self.fixtures}
        active_rotating = set(self.rotation_policy.active_rotating_case_ids())
        missing_active = sorted(active_rotating - set(by_id))
        if missing_active:
            raise ValueError(f"rotation_active_case_missing_manifest_entry:{missing_active}")
        non_rotating_active = sorted(
            case_id
            for case_id in active_rotating
            if by_id[case_id].split != UniversalCorpusSplit.ROTATING
        )
        if non_rotating_active:
            raise ValueError(f"rotation_active_case_not_rotating_split:{non_rotating_active}")
        return self

    def entries_for_split(self, split: UniversalCorpusSplit) -> tuple[FixtureManifestEntry, ...]:
        """Return manifest entries for a split, respecting active rotating round ids."""

        entries = tuple(entry for entry in self.fixtures if entry.split == split)
        if split != UniversalCorpusSplit.ROTATING:
            return entries
        active_ids = set(self.rotation_policy.active_rotating_case_ids())
        if not active_ids:
            return entries
        return tuple(entry for entry in entries if entry.case_id in active_ids)


def default_universal_corpus_fixture_root() -> Path:
    """Return the repo-owned W11.D fixture root."""

    repo_root = Path(__file__).resolve().parents[4]
    return repo_root / "tests" / "fixtures" / "universal-corpus"


def load_universal_corpus_manifest(root: Path | str | None = None) -> UniversalCorpusManifest:
    """Load and validate the universal corpus manifest.

    Args:
        root: Optional fixture root. Defaults to `tests/fixtures/universal-corpus`.

    Returns:
        The strict manifest model.

    Raises:
        FixtureRotationError: If the active rotating round repeats a previous
            rotating case without a durable acknowledgement.
    """

    fixture_root = _fixture_root(root)
    payload = _read_json(fixture_root / "manifest.json")
    try:
        manifest = UniversalCorpusManifest.model_validate(payload)
    except ValidationError:
        raise
    _raise_rotation_policy_errors(manifest)
    return manifest


def load_universal_corpus_fixture(path: Path | str) -> UniversalCorpusFixture:
    """Load one W11.D per-case fixture file."""

    return UniversalCorpusFixture.model_validate(_read_json(Path(path)))


def load_universal_corpus_fixtures(
    root: Path | str | None = None,
    *,
    split: UniversalCorpusSplit | str | None = None,
    include_hidden: bool = True,
) -> tuple[UniversalCorpusFixture, ...]:
    """Load fixture files from the universal corpus pack.

    Args:
        root: Optional fixture root.
        split: Optional split filter.
        include_hidden: Whether hidden fixtures may be read. Loading all
            fixtures defaults to `True` for internal validators; split-specific
            selection defaults to hidden protection via
            `select_universal_corpus_fixtures`.

    Returns:
        Loaded and manifest-consistent fixtures.
    """

    manifest = load_universal_corpus_manifest(root)
    fixture_root = _fixture_root(root)
    entries = _select_entries(manifest, split=split, include_hidden=include_hidden)
    return tuple(_load_entry_fixture(fixture_root, entry) for entry in entries)


def select_universal_corpus_fixtures(
    root: Path | str | None = None,
    *,
    split: UniversalCorpusSplit | str,
    include_hidden: bool = False,
) -> tuple[UniversalCorpusFixture, ...]:
    """Select fixtures for one evaluation split.

    Hidden fixtures require explicit opt-in so public test code cannot
    accidentally train against holdout expectations.
    """

    return load_universal_corpus_fixtures(
        root,
        split=split,
        include_hidden=include_hidden,
    )


def _select_entries(
    manifest: UniversalCorpusManifest,
    *,
    split: UniversalCorpusSplit | str | None,
    include_hidden: bool,
) -> tuple[FixtureManifestEntry, ...]:
    if split is None:
        return manifest.fixtures
    split_value = UniversalCorpusSplit(split)
    if split_value == UniversalCorpusSplit.HIDDEN and not include_hidden:
        raise HiddenFixtureAccessError("hidden fixtures require explicit opt-in")
    return manifest.entries_for_split(split_value)


def _load_entry_fixture(
    fixture_root: Path,
    entry: FixtureManifestEntry,
) -> UniversalCorpusFixture:
    fixture = load_universal_corpus_fixture(fixture_root / entry.path)
    if fixture.case_id != entry.case_id:
        raise UniversalCorpusFixtureError(
            f"fixture_case_id_mismatch:{entry.case_id}:{fixture.case_id}"
        )
    if fixture.split != entry.split:
        raise UniversalCorpusFixtureError(
            f"fixture_split_mismatch:{entry.case_id}:{entry.split}:{fixture.split}"
        )
    if fixture.domain != entry.domain:
        raise UniversalCorpusFixtureError(
            f"fixture_domain_mismatch:{entry.case_id}:{entry.domain}:{fixture.domain}"
        )
    if set(fixture.intent.authority_levels) != set(entry.authority_levels):
        raise UniversalCorpusFixtureError(
            f"fixture_authority_levels_mismatch:{entry.case_id}"
        )
    return fixture


def _raise_rotation_policy_errors(manifest: UniversalCorpusManifest) -> None:
    missing_ack = manifest.rotation_policy.missing_consecutive_reuse_ack_case_ids()
    if missing_ack:
        cases = ",".join(missing_ack)
        raise FixtureRotationError(
            "rotating_fixture_consecutive_reuse: "
            f"case_ids={cases} round_id={manifest.rotation_policy.active_round_id} "
            "requires rotation acknowledgement"
        )


def _fixture_root(root: Path | str | None) -> Path:
    return default_universal_corpus_fixture_root() if root is None else Path(root)


def _read_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _required_text(value: object) -> str:
    text = _optional_text(value)
    if text is None:
        raise ValueError("required text field is empty")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    raw: Iterable[object]
    if isinstance(value, str):
        raw = (value,)
    elif isinstance(value, Iterable):
        raw = value
    else:
        raw = (value,)
    output: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return tuple(output)


__all__ = [
    "UNIVERSAL_CORPUS_FIXTURE_SCHEMA_VERSION",
    "UNIVERSAL_CORPUS_MANIFEST_SCHEMA_VERSION",
    "AdapterBindingExpectation",
    "ClaimEvidenceAnnotations",
    "CloseoutStateExpectation",
    "ExpectedAdapterBindings",
    "ExpectedClaimFamilies",
    "ExpectedCloseoutStates",
    "ExpectedFacetOutputs",
    "ExpectedObligationGraphSlice",
    "ExpectedProjectionTruthfulness",
    "ExpectedRequirementSpecs",
    "FixtureManifestEntry",
    "FixtureRotationError",
    "HiddenFixtureAccessError",
    "PolicyIntentFixture",
    "ProjectionTruthfulnessExpectation",
    "RotationAcknowledgement",
    "RotationPolicy",
    "RotationRound",
    "UniversalCorpusFixture",
    "UniversalCorpusFixtureError",
    "UniversalCorpusManifest",
    "UniversalCorpusSplit",
    "default_universal_corpus_fixture_root",
    "load_universal_corpus_fixture",
    "load_universal_corpus_fixtures",
    "load_universal_corpus_manifest",
    "select_universal_corpus_fixtures",
]
