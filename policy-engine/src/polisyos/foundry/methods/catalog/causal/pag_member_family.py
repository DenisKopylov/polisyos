"""Bounded finite no-selection PAG member producer with exact observational membership checks."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import itertools
import json
import math
import time
from collections import deque
from collections.abc import Callable, Iterable, Mapping
from enum import Enum
from pathlib import Path
from typing import Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    PAGIdentificationPolicy,
    graph_content_sha256,
)

PROFILE_ID = "pag.no_selection.finite_member_sensitivity"
PROFILE_REVISION = "1"
_BACKEND_ID = "causal-learn.FCI.fci+d_separation"
_BACKEND_VERSION = "0.1.4.4"
_FCI_SOURCE_SHA256 = "8f0f14f9d31847efa30fa056a162f1f9d21d07595880c1ad2b099ec11e544ead"
_CIT_SOURCE_SHA256 = "0d3db11083985b7cb0edbaa44662307c28f27bc135053a65751cd52f451ddc8f"
_FAS_SOURCE_SHA256 = "d8bb8d61ca105a449ab5132d45de7934b924a35aa623c6aaac9ba8b26b95fd5a"
_NETWORKX_BACKEND_VERSION = "3.6.1"
_NETWORKX_D_SEPARATION_SOURCE_SHA256 = (
    "0e93a5d58688fbbdbf7e0509d8d2373e2ba3ec441143cc66c8040245d2e08d3c"
)
_WORK_ALGORITHM_ID = "causal-learn.FCI+FAS/CIT.d_separation+NetworkX.is_d_separator"
_CANONICAL_JSON = {
    "sort_keys": True,
    "separators": (",", ":"),
    "ensure_ascii": False,
    "allow_nan": False,
}


class PAGProposalDisposition(str, Enum):
    """Terminal result for one generated endpoint assignment."""

    ADMITTED = "admitted"
    DUPLICATE = "duplicate"
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"
    VALIDATION_INCOMPLETE = "validation_incomplete"


class PAGMemberFamilyStatus(str, Enum):
    """Whether the selected finite endpoint-assignment family was fully processed."""

    COMPLETED = "completed"
    UNSUPPORTED = "unsupported"
    BUDGET_EXHAUSTED = "budget_exhausted"
    VALIDATION_INCOMPLETE = "validation_incomplete"
    NOT_ESTABLISHED = "not_established"


class PAGMemberFamilyCoverage(str, Enum):
    """Coverage statement for the selected finite proposal family only."""

    FINITE_ENDPOINT_ASSIGNMENT_SPACE_COMPLETE = "finite_endpoint_assignment_space_complete"
    NOT_ESTABLISHED = "not_established"


class PAGMemberBudget(BaseModel):
    """Required caller-provided limits for one bounded producer invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_proposals: int = Field(ge=0)
    max_members: int = Field(ge=0)
    max_oracle_operations: int = Field(ge=0)
    max_elapsed_seconds: float = Field(ge=0)
    max_output_bytes: int = Field(ge=1024)

    @model_validator(mode="after")
    def _finite_elapsed_limit(self) -> PAGMemberBudget:
        if not math.isfinite(self.max_elapsed_seconds):
            raise ValueError("max_elapsed_seconds must be finite")
        return self


class PAGBackendIdentity(BaseModel):
    """Implementation identity for the admitted FCI+d-separation membership oracle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend_id: str
    backend_version: str
    fci_source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    cit_source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    adapter_source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class PAGWorkEstimateErrorCode(str, Enum):
    """Stable reason for refusing a PAG work estimate."""

    SOURCE_GRAPH_CONTENT_INVALID = "source_graph_content_invalid"
    UNSUPPORTED_GRAPH_OR_PROFILE = "unsupported_graph_or_profile"
    PINNED_BACKEND_IDENTITY_UNAVAILABLE = "pinned_backend_identity_unavailable"
    WORK_LIMIT_INVALID = "work_limit_invalid"
    ESTIMATOR_SOURCE_UNAVAILABLE = "estimator_source_unavailable"


class PAGWorkEstimateError(RuntimeError):
    """Fail-closed error raised when a trustworthy work estimate cannot be built."""

    def __init__(
        self,
        code: PAGWorkEstimateErrorCode | str,
        *,
        detail: str | None = None,
    ) -> None:
        self.code = code.value if isinstance(code, PAGWorkEstimateErrorCode) else code
        self.detail = detail
        super().__init__(self.code)


class PAGMemberWorkAlgorithmIdentityV1(BaseModel):
    """Content identity for the exact backend stack used by PAG membership checks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"] = "1"
    algorithm_id: Literal["causal-learn.FCI+FAS/CIT.d_separation+NetworkX.is_d_separator"] = (
        _WORK_ALGORITHM_ID
    )
    causal_learn_version: Literal["0.1.4.4"] = _BACKEND_VERSION
    networkx_version: Literal["3.6.1"] = _NETWORKX_BACKEND_VERSION
    fci_source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    cit_source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    fas_source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    networkx_d_separation_source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    adapter_source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class PAGFactoredPowerV1(BaseModel):
    """Exact power-of-two assignment space without constructing the integer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base: Literal[2] = 2
    exponent: StrictInt = Field(ge=0)


class PAGCappedBoundV1(BaseModel):
    """Exact count up to a ceiling, then the ceiling-plus-one overflow sentinel."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: StrictInt = Field(ge=0)
    ceiling: StrictInt = Field(ge=0)
    exceeded_ceiling: StrictBool

    @model_validator(mode="after")
    def _sentinel_reconciles(self) -> PAGCappedBoundV1:
        if self.exceeded_ceiling:
            if self.value != self.ceiling + 1:
                raise ValueError("exceeded_work_bound_requires_ceiling_plus_one_sentinel")
        elif self.value > self.ceiling:
            raise ValueError("exact_work_bound_cannot_exceed_its_ceiling")
        return self


class PAGMemberWorkEstimateV1(BaseModel):
    """Method-owned, graph-derived resource bound for one finite PAG membership run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"] = "1"
    profile_id: str = Field(min_length=1)
    profile_revision: str = Field(min_length=1)
    graph_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    budget: PAGMemberBudget
    algorithm_identity: PAGMemberWorkAlgorithmIdentityV1
    observed_node_count: StrictInt = Field(ge=0)
    observed_edge_count: StrictInt = Field(ge=0)
    circle_endpoint_count: StrictInt = Field(ge=0)
    bidirected_edge_upper_bound: StrictInt = Field(ge=0)
    expanded_node_upper_bound: StrictInt = Field(ge=0)
    expanded_edge_upper_bound: StrictInt = Field(ge=0)
    assignment_space: PAGFactoredPowerV1
    proposal_bound: PAGCappedBoundV1
    fci_membership_call_bound: PAGCappedBoundV1
    d_separation_queries_per_fci_call_bound: PAGCappedBoundV1
    d_separation_query_bound: PAGCappedBoundV1
    d_separation_query_unit: Literal["d_separation_query_count"] = "d_separation_query_count"
    max_estimated_dsep_queries: StrictInt = Field(ge=0)
    expanded_graph_element_query_bound: PAGCappedBoundV1
    expanded_graph_element_query_unit: Literal["expanded_graph_element_query_units"] = (
        "expanded_graph_element_query_units"
    )
    max_estimated_expanded_graph_element_query_units: StrictInt = Field(ge=0)
    estimator_source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def _graph_and_limit_bindings_reconcile(self) -> PAGMemberWorkEstimateV1:
        if self.assignment_space.exponent != self.circle_endpoint_count:
            raise ValueError("assignment_power_must_bind_circle_endpoint_count")
        if self.bidirected_edge_upper_bound > self.observed_edge_count:
            raise ValueError("bidirected_edge_upper_bound_exceeds_observed_edges")
        if self.expanded_node_upper_bound != (
            self.observed_node_count + self.bidirected_edge_upper_bound
        ):
            raise ValueError("expanded_node_bound_does_not_reconcile")
        if self.expanded_edge_upper_bound != (
            self.observed_edge_count + self.bidirected_edge_upper_bound
        ):
            raise ValueError("expanded_edge_bound_does_not_reconcile")
        if self.proposal_bound.ceiling != self.budget.max_proposals:
            raise ValueError("proposal_work_bound_must_bind_producer_budget")
        if self.fci_membership_call_bound.ceiling != self.budget.max_oracle_operations:
            raise ValueError("fci_work_bound_must_bind_producer_budget")
        if self.d_separation_queries_per_fci_call_bound.ceiling != (
            self.max_estimated_dsep_queries
        ):
            raise ValueError("per_call_dsep_bound_must_bind_dsep_limit")
        if self.d_separation_query_bound.ceiling != self.max_estimated_dsep_queries:
            raise ValueError("dsep_work_bound_must_bind_dsep_limit")
        if (
            self.expanded_graph_element_query_bound.ceiling
            != self.max_estimated_expanded_graph_element_query_units
        ):
            raise ValueError("expanded_graph_work_bound_must_bind_expanded_limit")
        return self


class PAGProposalRecord(BaseModel):
    """Content-bound terminal disposition for one attempted assignment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ordinal: int = Field(ge=0)
    assignment_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    disposition: PAGProposalDisposition
    member_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    duplicate_of: int | None = Field(default=None, ge=0)
    reason_code: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _disposition_fields(self) -> PAGProposalRecord:
        if self.disposition is PAGProposalDisposition.ADMITTED:
            if (
                self.member_sha256 is None
                or self.duplicate_of is not None
                or self.reason_code is not None
            ):
                raise ValueError("admitted proposal requires only member_sha256")
        elif self.disposition is PAGProposalDisposition.DUPLICATE:
            if (
                self.member_sha256 is not None
                or self.duplicate_of is None
                or self.reason_code is not None
            ):
                raise ValueError("duplicate proposal requires only duplicate_of")
        elif (
            self.member_sha256 is not None
            or self.duplicate_of is not None
            or self.reason_code is None
        ):
            raise ValueError("non-admitted proposal requires only reason_code")
        return self


def _proposal_disposition_counts(
    proposals: Iterable[PAGProposalRecord],
) -> dict[PAGProposalDisposition, int]:
    counts = dict.fromkeys(PAGProposalDisposition, 0)
    for proposal in proposals:
        counts[proposal.disposition] += 1
    return counts


class PAGAdmittedMember(BaseModel):
    """A validated no-selection MAG represented losslessly as a DAG or ADMG."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_ordinal: int = Field(ge=0)
    assignment_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    member_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    graph: CausalGraphModel


class PAGMemberCounts(BaseModel):
    """Reconciled execution counts; exponentially large universe counts stay decimal text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assignment_space_size: str = Field(pattern=r"^(0|[1-9][0-9]*)$")
    proposals_attempted: int = Field(ge=0)
    unattempted_proposals: str = Field(pattern=r"^(0|[1-9][0-9]*)$")
    admitted: int = Field(ge=0)
    duplicate: int = Field(ge=0)
    invalid: int = Field(ge=0)
    unsupported: int = Field(ge=0)
    validation_incomplete: int = Field(ge=0)
    oracle_operations: int = Field(ge=0)

    @model_validator(mode="after")
    def _attempts_reconcile(self) -> PAGMemberCounts:
        for disposition in PAGProposalDisposition:
            if disposition.value not in type(self).model_fields:
                raise ValueError(
                    f"proposal disposition count field is missing for {disposition.value}"
                )
        terminal = sum(getattr(self, disposition.value) for disposition in PAGProposalDisposition)
        if terminal != self.proposals_attempted:
            raise ValueError("proposal disposition counts must reconcile to attempted proposals")
        reconciled_space = _add_decimal_text(
            _decimal_text(self.proposals_attempted), self.unattempted_proposals
        )
        if reconciled_space != self.assignment_space_size:
            raise ValueError(
                "assignment_space_size must equal proposals_attempted plus unattempted_proposals"
            )
        if self.oracle_operations > self.proposals_attempted:
            raise ValueError("oracle operations cannot exceed attempted proposals")
        if self.admitted > self.oracle_operations:
            raise ValueError("admitted proposals cannot exceed oracle operations")
        return self


class PAGMemberFamilyResult(BaseModel):
    """Candidate-grade result over one explicitly selected finite PAG completion family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str
    profile_revision: str
    source_graph_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    backend_identity: PAGBackendIdentity | None = None
    budget: PAGMemberBudget
    status: PAGMemberFamilyStatus
    coverage: PAGMemberFamilyCoverage
    reason_code: str | None = None
    assumptions: tuple[str, ...]
    deadline_scope: str = "between_oracle_calls_only"
    elapsed_seconds: float = Field(ge=0)
    proposals: tuple[PAGProposalRecord, ...]
    members: tuple[PAGAdmittedMember, ...]
    counts: PAGMemberCounts
    trace_bytes: int = Field(ge=0)
    trace_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def _result_reconciles(self) -> PAGMemberFamilyResult:
        if len(self.proposals) != self.counts.proposals_attempted:
            raise ValueError("proposal rows must equal the attempted proposal count")
        disposition_counts = _proposal_disposition_counts(self.proposals)
        for disposition, expected_count in disposition_counts.items():
            field_name = disposition.value
            if field_name not in type(self.counts).model_fields:
                raise ValueError(f"proposal disposition count field is missing for {field_name}")
            if getattr(self.counts, field_name) != expected_count:
                raise ValueError("proposal disposition counts must match the proposal rows")
        if len(self.members) != self.counts.admitted:
            raise ValueError("admitted member rows must equal admitted proposal count")
        if self.counts.oracle_operations > self.budget.max_oracle_operations:
            raise ValueError("oracle operations exceed caller budget")
        if self.counts.proposals_attempted > self.budget.max_proposals:
            raise ValueError("attempted proposals exceed caller budget")
        if self.counts.admitted > self.budget.max_members:
            raise ValueError("admitted members exceed caller budget")
        if self.coverage is PAGMemberFamilyCoverage.FINITE_ENDPOINT_ASSIGNMENT_SPACE_COMPLETE:
            if (
                self.status is not PAGMemberFamilyStatus.COMPLETED
                or self.counts.unattempted_proposals != "0"
            ):
                raise ValueError(
                    "complete finite coverage requires completed status and "
                    "zero unattempted proposals"
                )
        elif self.status is PAGMemberFamilyStatus.COMPLETED:
            raise ValueError("completed status must account for the entire finite proposal family")
        elif self.status is PAGMemberFamilyStatus.NOT_ESTABLISHED:
            if (
                self.coverage is not PAGMemberFamilyCoverage.NOT_ESTABLISHED
                or self.reason_code != "zero_admitted_members_not_established"
                or self.counts.admitted != 0
                or self.members
                or self.counts.unattempted_proposals != "0"
                or self.counts.assignment_space_size
                != _decimal_text(self.counts.proposals_attempted)
            ):
                raise ValueError(
                    "not_established requires a fully attempted zero-admitted proposal family"
                )
        exhausted_status = self.status in {
            PAGMemberFamilyStatus.COMPLETED,
            PAGMemberFamilyStatus.NOT_ESTABLISHED,
        }
        if exhausted_status:
            expected_ordinals = tuple(range(self.counts.proposals_attempted))
            actual_ordinals = tuple(proposal.ordinal for proposal in self.proposals)
            if actual_ordinals != expected_ordinals:
                raise ValueError("exhausted_proposal_ordinals_must_be_contiguous_from_zero")
            if (
                self.counts.unattempted_proposals != "0"
                or self.counts.assignment_space_size
                != _decimal_text(self.counts.proposals_attempted)
            ):
                raise ValueError("exhausted_proposal_partition_must_be_fully_attempted")
            if self.counts.validation_incomplete != 0 or any(
                proposal.disposition is PAGProposalDisposition.VALIDATION_INCOMPLETE
                for proposal in self.proposals
            ):
                raise ValueError(
                    "exhausted_proposal_partition_cannot_include_validation_incomplete"
                )
        if (
            self.coverage is PAGMemberFamilyCoverage.FINITE_ENDPOINT_ASSIGNMENT_SPACE_COMPLETE
            and not self.members
        ):
            raise ValueError("complete finite coverage requires positive member admission")

        proposal_ordinals: set[int] = set()
        admitted_links: dict[int, tuple[str, str]] = {}
        for proposal in self.proposals:
            if proposal.ordinal in proposal_ordinals:
                raise ValueError("proposal rows must have unique ordinals")
            proposal_ordinals.add(proposal.ordinal)
            if proposal.disposition is PAGProposalDisposition.ADMITTED:
                if proposal.member_sha256 is None:
                    raise ValueError("admitted proposal must carry a member digest")
                admitted_links[proposal.ordinal] = (
                    proposal.assignment_sha256,
                    proposal.member_sha256,
                )

        member_links: dict[int, tuple[str, str]] = {}
        for member in self.members:
            if member.proposal_ordinal in member_links:
                raise ValueError("member rows must have unique proposal ordinals")
            member_links[member.proposal_ordinal] = (
                member.assignment_sha256,
                member.member_sha256,
            )
        if member_links != admitted_links:
            raise ValueError("member rows must be a one-to-one match for admitted proposal links")
        return self


class _FCINode(Protocol):
    def get_name(self) -> str: ...


class _FCIGraphEdge(Protocol):
    def get_node1(self) -> _FCINode: ...

    def get_node2(self) -> _FCINode: ...

    def get_endpoint1(self) -> object: ...

    def get_endpoint2(self) -> object: ...


class _FCIResult(Protocol):
    def get_node_names(self) -> list[str]: ...

    def get_graph_edges(self) -> list[_FCIGraphEdge]: ...


class _NetworkXDiGraph(Protocol):
    def add_nodes_from(self, nodes: Iterable[int]) -> None: ...

    def add_edge(self, source: int, target: int) -> None: ...


class _NumpyModule(Protocol):
    def zeros(self, shape: tuple[int, int]) -> object: ...


class _NetworkXModule(Protocol):
    DiGraph: Callable[[], _NetworkXDiGraph]


_FCICall = Callable[..., tuple[_FCIResult, object]]


class _BackendUnavailableError(RuntimeError):
    """The exact pinned structural membership backend is absent or changed."""


def _capped_power_product(
    coefficient: int, exponent: int, factors: Iterable[int], ceiling: int
) -> PAGCappedBoundV1:
    """Compare coefficient times 2**exponent and factors without constructing a huge power."""
    if coefficient < 0 or exponent < 0 or ceiling < 0:
        raise ValueError("work_bound_inputs_must_be_nonnegative")
    value = coefficient
    for factor in factors:
        if factor < 0:
            raise ValueError("work_bound_inputs_must_be_nonnegative")
        if factor == 0 or value == 0:
            return PAGCappedBoundV1(value=0, ceiling=ceiling, exceeded_ceiling=False)
        if value > ceiling // factor:
            return PAGCappedBoundV1(value=ceiling + 1, ceiling=ceiling, exceeded_ceiling=True)
        value *= factor
    if value == 0:
        return PAGCappedBoundV1(value=0, ceiling=ceiling, exceeded_ceiling=False)
    quotient = ceiling // value
    if exponent >= quotient.bit_length():
        return PAGCappedBoundV1(value=ceiling + 1, ceiling=ceiling, exceeded_ceiling=True)
    exact = value * (1 << exponent)
    return PAGCappedBoundV1(value=exact, ceiling=ceiling, exceeded_ceiling=False)


def _capped_exact_count(value: int, ceiling: int) -> PAGCappedBoundV1:
    if value > ceiling:
        return PAGCappedBoundV1(value=ceiling + 1, ceiling=ceiling, exceeded_ceiling=True)
    return PAGCappedBoundV1(value=value, ceiling=ceiling, exceeded_ceiling=False)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, **_CANONICAL_JSON).encode("utf-8")


def _decimal_text(value: int) -> str:
    """Render arbitrary-size nonnegative integers without Python's decimal digit cap."""
    if value < 0:
        raise ValueError("decimal count must be nonnegative")
    if value < 1_000_000_000:
        return str(value)
    chunks: list[int] = []
    while value:
        value, remainder = divmod(value, 1_000_000_000)
        chunks.append(remainder)
    return str(chunks[-1]) + "".join(f"{chunk:09d}" for chunk in reversed(chunks[:-1]))


def _add_decimal_text(left: str, right: str) -> str:
    """Add canonical nonnegative decimal strings without integer conversion limits."""
    left_index = len(left) - 1
    right_index = len(right) - 1
    carry = 0
    digits: list[str] = []
    while left_index >= 0 or right_index >= 0 or carry:
        total = carry
        if left_index >= 0:
            total += ord(left[left_index]) - ord("0")
            left_index -= 1
        if right_index >= 0:
            total += ord(right[right_index]) - ord("0")
            right_index -= 1
        digits.append(chr(ord("0") + total % 10))
        carry = total // 10
    return "".join(reversed(digits)) or "0"


def _source_endpoint_map(
    graph: CausalGraphModel,
) -> dict[tuple[str, str], tuple[EdgeMark, EdgeMark]]:
    endpoint_map: dict[tuple[str, str], tuple[EdgeMark, EdgeMark]] = {}
    for edge in graph.edges:
        left, right = sorted((edge.src, edge.dst))
        marks_by_node = {edge.src: edge.mark_src, edge.dst: edge.mark_dst}
        endpoint_map[(left, right)] = (marks_by_node[left], marks_by_node[right])
    return endpoint_map


def _edge_is_directed_or_bidirected(marks: tuple[EdgeMark, EdgeMark]) -> bool:
    left, right = marks
    return (left, right) in {
        (EdgeMark.TAIL, EdgeMark.ARROW),
        (EdgeMark.ARROW, EdgeMark.TAIL),
        (EdgeMark.ARROW, EdgeMark.ARROW),
    }


def _unsupported_source_reason(
    graph: CausalGraphModel, profile_id: str, profile_revision: str
) -> str | None:
    if profile_id != PROFILE_ID or profile_revision != PROFILE_REVISION:
        return "profile_not_registered"
    if graph.graph_type is not GraphType.PAG:
        return "input_graph_type_unsupported"
    if "rfci" in graph.discovery_method.casefold():
        return "rfci_incomplete_semantics_unsupported"
    for edge in graph.edges:
        if edge.lag is not None:
            return "lagged_graph_unsupported"
        marks = _source_endpoint_map(
            CausalGraphModel.model_construct(
                graph_type=GraphType.PAG, nodes=list(graph.nodes), edges=[edge]
            )
        )[(min(edge.src, edge.dst), max(edge.src, edge.dst))]
        if marks[0] is EdgeMark.TAIL and marks[1] is EdgeMark.TAIL:
            return "selection_encoded_tail_tail_unsupported"
        if EdgeMark.CIRCLE in marks and EdgeMark.TAIL in marks:
            return "circle_tail_endpoint_unsupported"
        if (
            EdgeMark.CIRCLE in marks
            and EdgeMark.ARROW not in marks
            and marks
            != (
                EdgeMark.CIRCLE,
                EdgeMark.CIRCLE,
            )
        ):
            return "endpoint_pattern_unsupported"
    metadata = graph.metadata
    if isinstance(metadata, Mapping):
        for raw_key, value in metadata.items():
            key = str(raw_key).casefold().replace("-", "_")
            if not value:
                continue
            if "background" in key:
                return "background_refined_pag_unsupported"
            if any(
                token in key for token in ("selection_node", "sample_selection", "selection_bias")
            ):
                return "selection_context_unsupported"
    return None


def _circle_slots(
    endpoint_map: Mapping[tuple[str, str], tuple[EdgeMark, EdgeMark]],
) -> tuple[tuple[str, str, int], ...]:
    return tuple(
        (left, right, side)
        for (left, right), marks in sorted(endpoint_map.items())
        for side, mark in enumerate(marks)
        if mark is EdgeMark.CIRCLE
    )


def _baseline_circle_values(
    endpoint_map: Mapping[tuple[str, str], tuple[EdgeMark, EdgeMark]],
    circle_slots: tuple[tuple[str, str, int], ...],
) -> tuple[EdgeMark, ...]:
    """Choose the first completion without introducing selection marks."""
    values: list[EdgeMark] = []
    for left, right, side in circle_slots:
        marks = endpoint_map[(left, right)]
        values.append(
            EdgeMark.ARROW
            if marks == (EdgeMark.CIRCLE, EdgeMark.CIRCLE) and side == 1
            else EdgeMark.TAIL
        )
    return tuple(values)


def _assignment_marks(
    endpoint_map: Mapping[tuple[str, str], tuple[EdgeMark, EdgeMark]],
    circle_slots: tuple[tuple[str, str, int], ...],
    baseline: tuple[EdgeMark, ...],
    flips: tuple[bool, ...],
) -> dict[tuple[str, str], tuple[EdgeMark, EdgeMark]]:
    assignments = dict(endpoint_map)
    for (left, right, side), baseline_mark, flip in zip(circle_slots, baseline, flips, strict=True):
        value = (
            (EdgeMark.ARROW if baseline_mark is EdgeMark.TAIL else EdgeMark.TAIL)
            if flip
            else baseline_mark
        )
        marks = list(assignments[(left, right)])
        marks[side] = value
        assignments[(left, right)] = (marks[0], marks[1])
    return assignments


def _assignment_digest(
    source_sha256: str,
    profile_id: str,
    profile_revision: str,
    ordinal: int,
    endpoint_map: Mapping[tuple[str, str], tuple[EdgeMark, EdgeMark]],
) -> str:
    marks = [
        [left, right, left_mark.value, right_mark.value]
        for (left, right), (left_mark, right_mark) in sorted(endpoint_map.items())
    ]
    return _sha256_bytes(
        _canonical_json_bytes(
            {
                "source_graph_sha256": source_sha256,
                "profile_id": profile_id,
                "profile_revision": profile_revision,
                "proposal_ordinal": ordinal,
                "endpoint_marks": marks,
            }
        )
    )


def _make_member_graph(
    source: CausalGraphModel,
    endpoint_map: Mapping[tuple[str, str], tuple[EdgeMark, EdgeMark]],
) -> CausalGraphModel:
    edges: list[CausalEdge] = []
    source_edges = {tuple(sorted((edge.src, edge.dst))): edge for edge in source.edges}
    bidirected = False
    for (left, right), (mark_left, mark_right) in sorted(endpoint_map.items()):
        if mark_left is EdgeMark.TAIL and mark_right is EdgeMark.TAIL:
            raise ValueError("tail_tail_selection_pattern")
        if mark_left is EdgeMark.CIRCLE or mark_right is EdgeMark.CIRCLE:
            raise ValueError("unresolved_circle_endpoint")
        if (mark_left, mark_right) == (EdgeMark.TAIL, EdgeMark.ARROW):
            src, dst = left, right
            mark_src, mark_dst = EdgeMark.TAIL, EdgeMark.ARROW
        elif (mark_left, mark_right) == (EdgeMark.ARROW, EdgeMark.TAIL):
            src, dst = right, left
            mark_src, mark_dst = EdgeMark.TAIL, EdgeMark.ARROW
        elif mark_left is EdgeMark.ARROW and mark_right is EdgeMark.ARROW:
            src, dst = left, right
            mark_src, mark_dst = EdgeMark.ARROW, EdgeMark.ARROW
            bidirected = True
        else:
            raise ValueError("unsupported_member_endpoint_pattern")
        source_edge = source_edges[(left, right)]
        edge_fields = source_edge.model_dump(mode="python")
        edge_fields.update(
            src=src,
            dst=dst,
            mark_src=mark_src,
            mark_dst=mark_dst,
        )
        edges.append(CausalEdge.model_validate(edge_fields))
    return CausalGraphModel(
        schema_version=source.schema_version,
        graph_type=GraphType.ADMG if bidirected else GraphType.DAG,
        nodes=sorted(source.nodes),
        edges=edges,
        discovery_method=source.discovery_method,
        skg_version_id=source.skg_version_id,
        pag_identification_policy=PAGIdentificationPolicy.CONSERVATIVE,
        id_confidence_under_pag=None,
        metadata=dict(source.metadata),
    )


def _directed_path(adjacency: Mapping[str, set[str]], start: str, target: str) -> bool:
    pending = [start]
    visited: set[str] = set()
    while pending:
        node = pending.pop()
        if node == target:
            return True
        if node in visited:
            continue
        visited.add(node)
        pending.extend(adjacency.get(node, ()))
    return False


def _directed_cycle(adjacency: Mapping[str, set[str]]) -> bool:
    indegree = dict.fromkeys(adjacency, 0)
    for children in adjacency.values():
        for child in children:
            indegree[child] += 1
    pending = deque(sorted(node for node, degree in indegree.items() if degree == 0))
    removed = 0
    while pending:
        node = pending.popleft()
        removed += 1
        for child in sorted(adjacency.get(node, ())):
            indegree[child] -= 1
            if indegree[child] == 0:
                pending.append(child)
    return removed != len(indegree)


def _ancestors(target: str, reverse: Mapping[str, set[str]]) -> set[str]:
    ancestors = {target}
    pending = [target]
    while pending:
        node = pending.pop()
        for parent in reverse.get(node, ()):
            if parent not in ancestors:
                ancestors.add(parent)
                pending.append(parent)
    return ancestors


def _has_inducing_path(
    first: str,
    second: str,
    adjacency: Mapping[tuple[str, str], tuple[EdgeMark, EdgeMark]],
    bidirected: Mapping[str, set[str]],
    reverse: Mapping[str, set[str]],
) -> bool:
    eligible = (_ancestors(first, reverse) | _ancestors(second, reverse)) - {first, second}
    if not eligible:
        return False

    def arrowhead_at(pair: tuple[str, str], node: str) -> bool:
        left, _right = pair
        marks = adjacency[pair]
        return marks[0] is EdgeMark.ARROW if node == left else marks[1] is EdgeMark.ARROW

    starts = {
        node
        for node in eligible
        if (min(first, node), max(first, node)) in adjacency
        and arrowhead_at((min(first, node), max(first, node)), node)
    }
    targets = {
        node
        for node in eligible
        if (min(second, node), max(second, node)) in adjacency
        and arrowhead_at((min(second, node), max(second, node)), node)
    }
    if not starts or not targets:
        return False
    pending = deque(sorted(starts))
    visited = set(starts)
    while pending:
        node = pending.popleft()
        if node in targets:
            return True
        for neighbor in sorted(bidirected.get(node, ()) & eligible):
            if neighbor not in visited:
                visited.add(neighbor)
                pending.append(neighbor)
    return False


def _structural_reason(
    nodes: list[str] | tuple[str, ...],
    adjacency_map: Mapping[tuple[str, str], tuple[EdgeMark, EdgeMark]],
) -> str | None:
    directed: dict[str, set[str]] = {node: set() for node in nodes}
    reverse: dict[str, set[str]] = {node: set() for node in nodes}
    bidirected: dict[str, set[str]] = {node: set() for node in nodes}
    adjacent: set[frozenset[str]] = set()
    for (left, right), marks in adjacency_map.items():
        adjacent.add(frozenset((left, right)))
        if marks == (EdgeMark.TAIL, EdgeMark.ARROW):
            directed[left].add(right)
            reverse[right].add(left)
        elif marks == (EdgeMark.ARROW, EdgeMark.TAIL):
            directed[right].add(left)
            reverse[left].add(right)
        elif marks == (EdgeMark.ARROW, EdgeMark.ARROW):
            bidirected[left].add(right)
            bidirected[right].add(left)
        else:
            return "unsupported_member_endpoint_pattern"
    if _directed_cycle(directed):
        return "directed_cycle"
    for left, neighbors in bidirected.items():
        for right in neighbors:
            if left < right and (
                _directed_path(directed, left, right) or _directed_path(directed, right, left)
            ):
                return "arrowhead_ancestry_violation"
    ordered_nodes = sorted(nodes)
    for index, first in enumerate(ordered_nodes):
        for second in ordered_nodes[index + 1 :]:
            if frozenset((first, second)) in adjacent:
                continue
            if _has_inducing_path(first, second, adjacency_map, bidirected, reverse):
                return "nonmaximal_inducing_path"
    return None


def _backend_identity() -> tuple[PAGBackendIdentity, _FCICall, _NumpyModule, _NetworkXModule]:
    try:
        fci_module = importlib.import_module("causallearn.search.ConstraintBased.FCI")
        cit_module = importlib.import_module("causallearn.utils.cit")
        version = importlib.metadata.version("causal-learn")
        fci_path = Path(fci_module.__file__ or "")
        cit_path = Path(cit_module.__file__ or "")
        fci_sha = _sha256_bytes(fci_path.read_bytes())
        cit_sha = _sha256_bytes(cit_path.read_bytes())
        adapter_sha = _sha256_bytes(Path(__file__).read_bytes())
        if (
            version != _BACKEND_VERSION
            or fci_sha != _FCI_SOURCE_SHA256
            or cit_sha != _CIT_SOURCE_SHA256
        ):
            raise _BackendUnavailableError("pinned_fci_backend_identity_mismatch")
        identity = PAGBackendIdentity(
            backend_id=_BACKEND_ID,
            backend_version=version,
            fci_source_sha256=fci_sha,
            cit_source_sha256=cit_sha,
            adapter_source_sha256=adapter_sha,
        )
        import networkx as nx
        import numpy as np

        return (
            identity,
            cast("_FCICall", fci_module.fci),
            cast("_NumpyModule", np),
            cast("_NetworkXModule", nx),
        )
    except _BackendUnavailableError:
        raise
    except Exception as exc:
        raise _BackendUnavailableError("pinned_fci_backend_unavailable") from exc


def pag_member_work_estimator_source_sha256() -> str:
    """Return the content hash of the currently imported PAG producer and estimator."""
    try:
        return _sha256_bytes(Path(__file__).read_bytes())
    except Exception as exc:
        raise PAGWorkEstimateError(
            PAGWorkEstimateErrorCode.ESTIMATOR_SOURCE_UNAVAILABLE,
            detail=type(exc).__name__,
        ) from exc


def pag_member_work_algorithm_identity() -> PAGMemberWorkAlgorithmIdentityV1:
    """Resolve and verify the pinned FCI, FAS, CIT, and NetworkX d-separation stack."""
    try:
        backend, _, _, _ = _backend_identity()
        fas_module = importlib.import_module("causallearn.utils.FAS")
        networkx_module = importlib.import_module("networkx")
        dsep_module = importlib.import_module("networkx.algorithms.d_separation")
        networkx_version = importlib.metadata.version("networkx")
        fas_path = Path(fas_module.__file__ or "")
        dsep_path = Path(dsep_module.__file__ or "")
        fas_sha = _sha256_bytes(fas_path.read_bytes())
        dsep_sha = _sha256_bytes(dsep_path.read_bytes())
        if (
            fas_sha != _FAS_SOURCE_SHA256
            or networkx_version != _NETWORKX_BACKEND_VERSION
            or dsep_sha != _NETWORKX_D_SEPARATION_SOURCE_SHA256
            or getattr(networkx_module, "is_d_separator", None)
            is not getattr(dsep_module, "is_d_separator", None)
        ):
            raise PAGWorkEstimateError(
                PAGWorkEstimateErrorCode.PINNED_BACKEND_IDENTITY_UNAVAILABLE,
                detail="pinned_fas_or_networkx_dsep_identity_mismatch",
            )
        return PAGMemberWorkAlgorithmIdentityV1(
            algorithm_id=_WORK_ALGORITHM_ID,
            causal_learn_version=backend.backend_version,
            networkx_version=networkx_version,
            fci_source_sha256=backend.fci_source_sha256,
            cit_source_sha256=backend.cit_source_sha256,
            fas_source_sha256=fas_sha,
            networkx_d_separation_source_sha256=dsep_sha,
            adapter_source_sha256=backend.adapter_source_sha256,
        )
    except PAGWorkEstimateError:
        raise
    except Exception as exc:
        raise PAGWorkEstimateError(
            PAGWorkEstimateErrorCode.PINNED_BACKEND_IDENTITY_UNAVAILABLE,
            detail=type(exc).__name__,
        ) from exc


def pag_member_work_estimate_sha256(estimate: PAGMemberWorkEstimateV1) -> str:
    """Hash the canonical serialized method-owned work estimate."""
    return _sha256_bytes(_canonical_json_bytes(estimate.model_dump(mode="json")))


def estimate_pag_member_work(
    graph: CausalGraphModel,
    *,
    profile_id: str = PROFILE_ID,
    profile_revision: str = PROFILE_REVISION,
    budget: PAGMemberBudget,
    max_estimated_dsep_queries: int,
    max_estimated_expanded_graph_element_query_units: int,
) -> PAGMemberWorkEstimateV1:
    """Estimate finite PAG membership work in bounded, graph-derived query units.

    The d-separation bound counts unique endpoint/conditioning-set keys per full
    FCI membership call: choose two observed endpoints and any subset of the
    remaining observed nodes. Expanded-graph units multiply that bound by the
    conservative expanded node-plus-edge count. Neither unit estimates elapsed
    time or claims a count of backend instructions.
    """
    if type(max_estimated_dsep_queries) is not int or max_estimated_dsep_queries < 0:
        raise PAGWorkEstimateError(PAGWorkEstimateErrorCode.WORK_LIMIT_INVALID)
    if (
        type(max_estimated_expanded_graph_element_query_units) is not int
        or max_estimated_expanded_graph_element_query_units < 0
    ):
        raise PAGWorkEstimateError(PAGWorkEstimateErrorCode.WORK_LIMIT_INVALID)
    try:
        graph_sha = graph_content_sha256(graph)
    except Exception as exc:
        raise PAGWorkEstimateError(
            PAGWorkEstimateErrorCode.SOURCE_GRAPH_CONTENT_INVALID,
            detail=type(exc).__name__,
        ) from exc
    unsupported = _unsupported_source_reason(graph, profile_id, profile_revision)
    if unsupported is not None:
        raise PAGWorkEstimateError(
            PAGWorkEstimateErrorCode.UNSUPPORTED_GRAPH_OR_PROFILE,
            detail=unsupported,
        )
    try:
        endpoint_map = _source_endpoint_map(graph)
        circle_count = len(_circle_slots(endpoint_map))
        algorithm_identity = pag_member_work_algorithm_identity()
        estimator_sha = pag_member_work_estimator_source_sha256()
    except PAGWorkEstimateError:
        raise
    except Exception as exc:
        raise PAGWorkEstimateError(
            PAGWorkEstimateErrorCode.SOURCE_GRAPH_CONTENT_INVALID,
            detail=type(exc).__name__,
        ) from exc

    observed_nodes = len(graph.nodes)
    observed_edges = len(graph.edges)
    bidirected_upper = sum(
        1 for marks in endpoint_map.values() if all(mark is not EdgeMark.TAIL for mark in marks)
    )
    expanded_nodes = observed_nodes + bidirected_upper
    expanded_edges = observed_edges + bidirected_upper

    proposal_demand = _capped_power_product(1, circle_count, (), budget.max_proposals)
    proposal_count = (
        budget.max_proposals if proposal_demand.exceeded_ceiling else proposal_demand.value
    )
    fci_demand_count = 0 if budget.max_members == 0 else proposal_count
    fci_call_bound = _capped_exact_count(fci_demand_count, budget.max_oracle_operations)
    permitted_fci_calls = min(fci_demand_count, budget.max_oracle_operations)

    endpoint_pair_count = observed_nodes * (observed_nodes - 1) // 2
    conditioning_power = max(0, observed_nodes - 2)
    per_call_bound = _capped_power_product(
        endpoint_pair_count,
        conditioning_power,
        (),
        max_estimated_dsep_queries,
    )
    dsep_bound = _capped_power_product(
        endpoint_pair_count,
        conditioning_power,
        (permitted_fci_calls,),
        max_estimated_dsep_queries,
    )
    expanded_element_count = expanded_nodes + expanded_edges
    expanded_bound = _capped_power_product(
        endpoint_pair_count,
        conditioning_power,
        (permitted_fci_calls, expanded_element_count),
        max_estimated_expanded_graph_element_query_units,
    )
    return PAGMemberWorkEstimateV1(
        profile_id=profile_id,
        profile_revision=profile_revision,
        graph_sha256=graph_sha,
        budget=budget,
        algorithm_identity=algorithm_identity,
        observed_node_count=observed_nodes,
        observed_edge_count=observed_edges,
        circle_endpoint_count=circle_count,
        bidirected_edge_upper_bound=bidirected_upper,
        expanded_node_upper_bound=expanded_nodes,
        expanded_edge_upper_bound=expanded_edges,
        assignment_space=PAGFactoredPowerV1(base=2, exponent=circle_count),
        proposal_bound=proposal_demand,
        fci_membership_call_bound=fci_call_bound,
        d_separation_queries_per_fci_call_bound=per_call_bound,
        d_separation_query_bound=dsep_bound,
        max_estimated_dsep_queries=max_estimated_dsep_queries,
        expanded_graph_element_query_bound=expanded_bound,
        max_estimated_expanded_graph_element_query_units=(
            max_estimated_expanded_graph_element_query_units
        ),
        estimator_source_sha256=estimator_sha,
    )


def _oracle_pag_endpoint_map(
    graph: CausalGraphModel,
    fci: _FCICall,
    numpy: _NumpyModule,
    networkx: _NetworkXModule,
) -> tuple[tuple[str, ...], dict[tuple[str, str], tuple[EdgeMark, EdgeMark]]]:
    observed = tuple(sorted(graph.nodes))
    observed_index = {name: index for index, name in enumerate(observed)}
    latent_edges = [
        (left, right)
        for (left, right), marks in sorted(_source_endpoint_map(graph).items())
        if marks == (EdgeMark.ARROW, EdgeMark.ARROW)
    ]
    expanded = networkx.DiGraph()
    expanded.add_nodes_from(range(len(observed) + len(latent_edges)))
    latent_index = len(observed)
    for (left, right), (mark_left, mark_right) in _source_endpoint_map(graph).items():
        if mark_left is EdgeMark.TAIL and mark_right is EdgeMark.ARROW:
            expanded.add_edge(observed_index[left], observed_index[right])
        elif mark_left is EdgeMark.ARROW and mark_right is EdgeMark.TAIL:
            expanded.add_edge(observed_index[right], observed_index[left])
        elif mark_left is EdgeMark.ARROW and mark_right is EdgeMark.ARROW:
            expanded.add_edge(latent_index, observed_index[left])
            expanded.add_edge(latent_index, observed_index[right])
            latent_index += 1
        else:
            raise ValueError("membership oracle requires a resolved DAG/ADMG member")
    result, _ = fci(
        numpy.zeros((len(observed), len(observed))),
        independence_test_method="d_separation",
        true_dag=expanded,
        depth=-1,
        max_path_length=-1,
        verbose=False,
        show_progress=False,
        node_names=list(observed),
    )
    node_names = tuple(result.get_node_names())
    normalized: dict[tuple[str, str], tuple[EdgeMark, EdgeMark]] = {}
    endpoint_types = {
        "TAIL": EdgeMark.TAIL,
        "ARROW": EdgeMark.ARROW,
        "CIRCLE": EdgeMark.CIRCLE,
    }
    for edge in result.get_graph_edges():
        first = edge.get_node1().get_name()
        second = edge.get_node2().get_name()
        endpoint_first = endpoint_types.get(str(edge.get_endpoint1()).upper())
        endpoint_second = endpoint_types.get(str(edge.get_endpoint2()).upper())
        if endpoint_first is None or endpoint_second is None or first == second:
            raise ValueError("membership oracle returned unsupported endpoint data")
        if first < second:
            normalized[(first, second)] = (endpoint_first, endpoint_second)
        else:
            normalized[(second, first)] = (endpoint_second, endpoint_first)
    return node_names, normalized


def _trace_payload(
    *,
    profile_id: str,
    profile_revision: str,
    source_graph_sha256: str | None,
    backend_identity: PAGBackendIdentity | None,
    budget: PAGMemberBudget,
    status: PAGMemberFamilyStatus,
    coverage: PAGMemberFamilyCoverage,
    reason_code: str | None,
    proposals: list[PAGProposalRecord],
    members: list[PAGAdmittedMember],
    counts: PAGMemberCounts,
) -> bytes:
    payload = {
        "profile_id": profile_id,
        "profile_revision": profile_revision,
        "source_graph_sha256": source_graph_sha256,
        "backend_identity": None
        if backend_identity is None
        else backend_identity.model_dump(mode="json"),
        "budget": budget.model_dump(mode="json"),
        "status": status.value,
        "coverage": coverage.value,
        "reason_code": reason_code,
        "assumptions": [
            "complete_observational_pag_assumed_by_explicit_request",
            "hypothetical_no_sample_selection",
            "latent_confounding_allowed",
            "candidate_math_only_not_law_authority_calibration_or_real_world_truth",
        ],
        "deadline_scope": "between_oracle_calls_only",
        "proposals": [row.model_dump(mode="json") for row in proposals],
        "members": [
            {
                "proposal_ordinal": member.proposal_ordinal,
                "assignment_sha256": member.assignment_sha256,
                "member_sha256": member.member_sha256,
                "graph": member.graph.model_dump(mode="json"),
            }
            for member in members
        ],
        "counts": counts.model_dump(mode="json"),
    }
    return _canonical_json_bytes(payload)


def _make_result(
    *,
    profile_id: str,
    profile_revision: str,
    source_graph_sha256: str | None,
    backend_identity: PAGBackendIdentity | None,
    budget: PAGMemberBudget,
    status: PAGMemberFamilyStatus,
    coverage: PAGMemberFamilyCoverage,
    reason_code: str | None,
    proposals: list[PAGProposalRecord],
    members: list[PAGAdmittedMember],
    assignment_space_size: int,
    oracle_operations: int,
    started_at: float,
) -> PAGMemberFamilyResult:
    counts_by_disposition = _proposal_disposition_counts(proposals)
    unattempted = assignment_space_size - len(proposals)
    disposition_fields = {
        disposition.value: counts_by_disposition[disposition]
        for disposition in PAGProposalDisposition
    }
    counts = PAGMemberCounts(
        assignment_space_size=_decimal_text(assignment_space_size),
        proposals_attempted=len(proposals),
        unattempted_proposals=_decimal_text(unattempted),
        oracle_operations=oracle_operations,
        **disposition_fields,
    )
    assumptions = (
        "complete_observational_pag_assumed_by_explicit_request",
        "hypothetical_no_sample_selection",
        "latent_confounding_allowed",
        "candidate_math_only_not_law_authority_calibration_or_real_world_truth",
    )
    trace = _trace_payload(
        profile_id=profile_id,
        profile_revision=profile_revision,
        source_graph_sha256=source_graph_sha256,
        backend_identity=backend_identity,
        budget=budget,
        status=status,
        coverage=coverage,
        reason_code=reason_code,
        proposals=proposals,
        members=members,
        counts=counts,
    )
    elapsed = max(0.0, time.monotonic() - started_at)
    return PAGMemberFamilyResult(
        profile_id=profile_id,
        profile_revision=profile_revision,
        source_graph_sha256=source_graph_sha256,
        backend_identity=backend_identity,
        budget=budget,
        status=status,
        coverage=coverage,
        reason_code=reason_code,
        assumptions=assumptions,
        elapsed_seconds=elapsed,
        proposals=tuple(proposals),
        members=tuple(members),
        counts=counts,
        trace_bytes=len(trace),
        trace_sha256=_sha256_bytes(trace),
    )


def evaluate_pag_member_family(
    graph: CausalGraphModel,
    *,
    profile_id: str,
    profile_revision: str,
    budget: PAGMemberBudget,
) -> PAGMemberFamilyResult:
    """Stream and independently verify a finite family of no-selection PAG member proposals.

    Each proposed DAG/ADMG is checked for ancestry and maximality, then expanded with a fresh
    latent parent per bidirected edge and reconstructed through the pinned public FCI+d-separation
    API. Membership requires exact observed node, skeleton, and endpoint equality to the supplied
    complete PAG. This is conditional candidate mathematics, not a claim about law, authority,
    calibration, selection absence, or real-world graph truth.

    The elapsed-time budget is checked between synchronous oracle calls. The caller must place this
    function behind its existing supervised execution permit to enforce a hard deadline for a
    single non-interruptible third-party FCI call.
    """
    started = time.monotonic()
    source_sha: str | None = None
    try:
        source_sha = graph_content_sha256(graph)
    except Exception:
        return _make_result(
            profile_id=profile_id,
            profile_revision=profile_revision,
            source_graph_sha256=None,
            backend_identity=None,
            budget=budget,
            status=PAGMemberFamilyStatus.UNSUPPORTED,
            coverage=PAGMemberFamilyCoverage.NOT_ESTABLISHED,
            reason_code="source_graph_content_invalid",
            proposals=[],
            members=[],
            assignment_space_size=0,
            oracle_operations=0,
            started_at=started,
        )
    unsupported = _unsupported_source_reason(graph, profile_id, profile_revision)
    if unsupported is not None:
        return _make_result(
            profile_id=profile_id,
            profile_revision=profile_revision,
            source_graph_sha256=source_sha,
            backend_identity=None,
            budget=budget,
            status=PAGMemberFamilyStatus.UNSUPPORTED,
            coverage=PAGMemberFamilyCoverage.NOT_ESTABLISHED,
            reason_code=unsupported,
            proposals=[],
            members=[],
            assignment_space_size=0,
            oracle_operations=0,
            started_at=started,
        )

    endpoint_map = _source_endpoint_map(graph)
    circle_slots = _circle_slots(endpoint_map)
    baseline_values = _baseline_circle_values(endpoint_map, circle_slots)
    assignment_space_size = 1 << len(circle_slots)
    proposals: list[PAGProposalRecord] = []
    members: list[PAGAdmittedMember] = []
    seen_members: dict[str, int] = {}
    backend: PAGBackendIdentity | None = None
    fci: _FCICall | None = None
    numpy: _NumpyModule | None = None
    networkx: _NetworkXModule | None = None
    oracle_operations = 0
    terminal_status = PAGMemberFamilyStatus.COMPLETED
    terminal_reason: str | None = None

    for ordinal, flips in enumerate(itertools.product((False, True), repeat=len(circle_slots))):
        if ordinal >= assignment_space_size:
            terminal_status = PAGMemberFamilyStatus.COMPLETED
            terminal_reason = None
            break
        if len(proposals) >= budget.max_proposals:
            terminal_status = PAGMemberFamilyStatus.BUDGET_EXHAUSTED
            terminal_reason = "proposal_budget_exhausted"
            break
        if time.monotonic() - started >= budget.max_elapsed_seconds:
            terminal_status = PAGMemberFamilyStatus.BUDGET_EXHAUSTED
            terminal_reason = "elapsed_budget_exhausted_between_oracle_calls"
            break
        assigned = _assignment_marks(endpoint_map, circle_slots, baseline_values, flips)
        assignment_sha = _assignment_digest(
            source_sha,
            profile_id,
            profile_revision,
            ordinal,
            assigned,
        )

        if any(marks == (EdgeMark.TAIL, EdgeMark.TAIL) for marks in assigned.values()):
            row = PAGProposalRecord(
                ordinal=ordinal,
                assignment_sha256=assignment_sha,
                disposition=PAGProposalDisposition.UNSUPPORTED,
                reason_code="selection_encoded_tail_tail_outside_no_selection_profile",
            )
            next_rows = [*proposals, row]
            trial_counts = _counts_preview(assignment_space_size, next_rows, oracle_operations)
            if not _trace_fits(
                budget,
                profile_id,
                profile_revision,
                source_sha,
                backend,
                terminal_status,
                PAGMemberFamilyCoverage.NOT_ESTABLISHED,
                "output_budget_exhausted",
                next_rows,
                members,
                trial_counts,
            ):
                terminal_status = PAGMemberFamilyStatus.BUDGET_EXHAUSTED
                terminal_reason = "output_budget_exhausted"
                break
            proposals.append(row)
            continue

        structural_reason = _structural_reason(graph.nodes, assigned)
        if structural_reason is not None:
            row = PAGProposalRecord(
                ordinal=ordinal,
                assignment_sha256=assignment_sha,
                disposition=PAGProposalDisposition.INVALID,
                reason_code=structural_reason,
            )
            next_rows = [*proposals, row]
            trial_counts = _counts_preview(assignment_space_size, next_rows, oracle_operations)
            if not _trace_fits(
                budget,
                profile_id,
                profile_revision,
                source_sha,
                backend,
                PAGMemberFamilyStatus.BUDGET_EXHAUSTED,
                PAGMemberFamilyCoverage.NOT_ESTABLISHED,
                "output_budget_exhausted",
                next_rows,
                members,
                trial_counts,
            ):
                terminal_status = PAGMemberFamilyStatus.BUDGET_EXHAUSTED
                terminal_reason = "output_budget_exhausted"
                break
            proposals.append(row)
            continue

        try:
            candidate = _make_member_graph(graph, assigned)
        except Exception:
            row = PAGProposalRecord(
                ordinal=ordinal,
                assignment_sha256=assignment_sha,
                disposition=PAGProposalDisposition.INVALID,
                reason_code="member_graph_encoding_invalid",
            )
            next_rows = [*proposals, row]
            trial_counts = _counts_preview(assignment_space_size, next_rows, oracle_operations)
            if not _trace_fits(
                budget,
                profile_id,
                profile_revision,
                source_sha,
                backend,
                PAGMemberFamilyStatus.BUDGET_EXHAUSTED,
                PAGMemberFamilyCoverage.NOT_ESTABLISHED,
                "output_budget_exhausted",
                next_rows,
                members,
                trial_counts,
            ):
                terminal_status = PAGMemberFamilyStatus.BUDGET_EXHAUSTED
                terminal_reason = "output_budget_exhausted"
                break
            proposals.append(row)
            continue

        candidate_sha = graph_content_sha256(candidate)
        if candidate_sha in seen_members:
            row = PAGProposalRecord(
                ordinal=ordinal,
                assignment_sha256=assignment_sha,
                disposition=PAGProposalDisposition.DUPLICATE,
                duplicate_of=seen_members[candidate_sha],
            )
            next_rows = [*proposals, row]
            trial_counts = _counts_preview(assignment_space_size, next_rows, oracle_operations)
            if not _trace_fits(
                budget,
                profile_id,
                profile_revision,
                source_sha,
                backend,
                PAGMemberFamilyStatus.BUDGET_EXHAUSTED,
                PAGMemberFamilyCoverage.NOT_ESTABLISHED,
                "output_budget_exhausted",
                next_rows,
                members,
                trial_counts,
            ):
                terminal_status = PAGMemberFamilyStatus.BUDGET_EXHAUSTED
                terminal_reason = "output_budget_exhausted"
                break
            proposals.append(row)
            continue

        preflight_row = PAGProposalRecord(
            ordinal=ordinal,
            assignment_sha256=assignment_sha,
            disposition=PAGProposalDisposition.ADMITTED,
            member_sha256=candidate_sha,
        )
        preflight_member = PAGAdmittedMember(
            proposal_ordinal=ordinal,
            assignment_sha256=assignment_sha,
            member_sha256=candidate_sha,
            graph=candidate,
        )
        preflight_rows = [*proposals, preflight_row]
        preflight_members = [*members, preflight_member]
        preflight_counts = _counts_preview(
            assignment_space_size, preflight_rows, oracle_operations + 1
        )
        if (
            len(members) >= budget.max_members
            or oracle_operations >= budget.max_oracle_operations
            or time.monotonic() - started >= budget.max_elapsed_seconds
        ):
            reason = (
                "member_budget_exhausted"
                if len(members) >= budget.max_members
                else "oracle_operation_budget_exhausted"
                if oracle_operations >= budget.max_oracle_operations
                else "elapsed_budget_exhausted_between_oracle_calls"
            )
            incomplete = PAGProposalRecord(
                ordinal=ordinal,
                assignment_sha256=assignment_sha,
                disposition=PAGProposalDisposition.VALIDATION_INCOMPLETE,
                reason_code=reason,
            )
            next_rows = [*proposals, incomplete]
            actual_counts = _counts_preview(assignment_space_size, next_rows, oracle_operations)
            if not _trace_fits(
                budget,
                profile_id,
                profile_revision,
                source_sha,
                backend,
                PAGMemberFamilyStatus.VALIDATION_INCOMPLETE,
                PAGMemberFamilyCoverage.NOT_ESTABLISHED,
                reason,
                next_rows,
                members,
                actual_counts,
            ):
                terminal_status = PAGMemberFamilyStatus.BUDGET_EXHAUSTED
                terminal_reason = "output_budget_exhausted"
                break
            proposals.append(incomplete)
            terminal_status = PAGMemberFamilyStatus.VALIDATION_INCOMPLETE
            terminal_reason = reason
            break

        if not _trace_fits(
            budget,
            profile_id,
            profile_revision,
            source_sha,
            backend,
            PAGMemberFamilyStatus.BUDGET_EXHAUSTED,
            PAGMemberFamilyCoverage.NOT_ESTABLISHED,
            "output_budget_exhausted",
            preflight_rows,
            preflight_members,
            preflight_counts,
        ):
            terminal_status = PAGMemberFamilyStatus.BUDGET_EXHAUSTED
            terminal_reason = "output_budget_exhausted"
            break

        try:
            if backend is None:
                backend, fci, numpy, networkx = _backend_identity()
            if fci is None or numpy is None or networkx is None:
                raise _BackendUnavailableError("pinned_fci_backend_unavailable")
            oracle_operations += 1
            observed_names, reconstructed = _oracle_pag_endpoint_map(
                candidate, fci, numpy, networkx
            )
            if set(observed_names) != set(graph.nodes):
                raise ValueError("membership_oracle_observed_node_identity_mismatch")
        except _BackendUnavailableError as exc:
            reason = str(exc) or "pinned_fci_backend_unavailable"
            row = PAGProposalRecord(
                ordinal=ordinal,
                assignment_sha256=assignment_sha,
                disposition=PAGProposalDisposition.VALIDATION_INCOMPLETE,
                reason_code=reason,
            )
            proposals.append(row)
            terminal_status = PAGMemberFamilyStatus.VALIDATION_INCOMPLETE
            terminal_reason = reason
            break
        except Exception:
            row = PAGProposalRecord(
                ordinal=ordinal,
                assignment_sha256=assignment_sha,
                disposition=PAGProposalDisposition.VALIDATION_INCOMPLETE,
                reason_code="membership_oracle_failed",
            )
            proposals.append(row)
            terminal_status = PAGMemberFamilyStatus.VALIDATION_INCOMPLETE
            terminal_reason = "membership_oracle_failed"
            break

        expected = _source_endpoint_map(graph)
        if reconstructed != expected:
            row = PAGProposalRecord(
                ordinal=ordinal,
                assignment_sha256=assignment_sha,
                disposition=PAGProposalDisposition.INVALID,
                reason_code="pag_membership_mismatch",
            )
            proposals.append(row)
            continue

        row = PAGProposalRecord(
            ordinal=ordinal,
            assignment_sha256=assignment_sha,
            disposition=PAGProposalDisposition.ADMITTED,
            member_sha256=candidate_sha,
        )
        proposals.append(row)
        members.append(preflight_member)
        seen_members[candidate_sha] = ordinal

    full_assignment_space_processed = len(proposals) == assignment_space_size
    coverage = (
        PAGMemberFamilyCoverage.FINITE_ENDPOINT_ASSIGNMENT_SPACE_COMPLETE
        if terminal_status is PAGMemberFamilyStatus.COMPLETED
        and full_assignment_space_processed
        and members
        else PAGMemberFamilyCoverage.NOT_ESTABLISHED
    )
    if (
        terminal_status is PAGMemberFamilyStatus.COMPLETED
        and coverage is PAGMemberFamilyCoverage.NOT_ESTABLISHED
    ):
        if full_assignment_space_processed and not members:
            terminal_status = PAGMemberFamilyStatus.NOT_ESTABLISHED
            terminal_reason = "zero_admitted_members_not_established"
        else:
            terminal_status = PAGMemberFamilyStatus.BUDGET_EXHAUSTED
            terminal_reason = "proposal_family_not_fully_processed"

    result = _make_result(
        profile_id=profile_id,
        profile_revision=profile_revision,
        source_graph_sha256=source_sha,
        backend_identity=backend,
        budget=budget,
        status=terminal_status,
        coverage=coverage,
        reason_code=terminal_reason,
        proposals=proposals,
        members=members,
        assignment_space_size=assignment_space_size,
        oracle_operations=oracle_operations,
        started_at=started,
    )
    if result.trace_bytes > budget.max_output_bytes:
        raise RuntimeError("producer_trace_output_budget_invariant_failed")
    return result


def _counts_preview(
    assignment_space_size: int,
    proposals: list[PAGProposalRecord],
    oracle_operations: int,
) -> PAGMemberCounts:
    disposition_fields = {
        disposition.value: count
        for disposition, count in _proposal_disposition_counts(proposals).items()
    }
    return PAGMemberCounts(
        assignment_space_size=_decimal_text(assignment_space_size),
        proposals_attempted=len(proposals),
        unattempted_proposals=_decimal_text(assignment_space_size - len(proposals)),
        oracle_operations=oracle_operations,
        **disposition_fields,
    )


def _trace_fits(
    budget: PAGMemberBudget,
    profile_id: str,
    profile_revision: str,
    source_graph_sha256: str | None,
    backend_identity: PAGBackendIdentity | None,
    status: PAGMemberFamilyStatus,
    coverage: PAGMemberFamilyCoverage,
    reason_code: str | None,
    proposals: list[PAGProposalRecord],
    members: list[PAGAdmittedMember],
    counts: PAGMemberCounts,
) -> bool:
    return (
        len(
            _trace_payload(
                profile_id=profile_id,
                profile_revision=profile_revision,
                source_graph_sha256=source_graph_sha256,
                backend_identity=backend_identity,
                budget=budget,
                status=status,
                coverage=coverage,
                reason_code=reason_code,
                proposals=proposals,
                members=members,
                counts=counts,
            )
        )
        + 512
        <= budget.max_output_bytes
    )
