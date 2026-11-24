"""Preselected historical comparison scope and deterministic pooled statistics."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping
from decimal import Decimal
from fractions import Fraction
from itertools import pairwise
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics._owner_admission import (
    OwnedJSONRepresentation,
    declare_model_owner,
    owner_profile_for_spec,
)
from polisyos.ir.artifacts import InputRef
from polisyos.ir.artifacts.io import _get_owned_json_artifact, _put_owned_json_artifact
from polisyos.ir.migrations.base import CompatibilityMode
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ArtifactRefModel

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from polisyos.ir.analytics.backtest import BacktestScenario, _BacktestErrorSummary
    from polisyos.ir.artifacts import ArtifactStore

_SELECTED_SHA256 = r"^sha256:[0-9a-f]{64}$"
_POLICY_KIND = "ir.backtest_pooling_policy"
_POLICY_ROLE = "backtest_pooling_policy"
_CANON = CanonSpec(forbid_floats=False)


class SelectedRepresentationRef(ArtifactRefModel):
    """IR handle for an exact existing Catalog measurement representation."""

    kind: Literal["catalog.variable_representation"] = "catalog.variable_representation"
    media_type: Literal["application/json"] = "application/json"
    manifest_profile_sha256: str = Field(pattern=_SELECTED_SHA256)


class SelectedDefinitionRef(ArtifactRefModel):
    """IR handle for the existing Catalog semantic definition."""

    kind: Literal["catalog.variable_semantic_definition"] = "catalog.variable_semantic_definition"
    media_type: Literal["application/json"] = "application/json"
    manifest_profile_sha256: str = Field(pattern=_SELECTED_SHA256)


class SelectedHistoricalRowsRef(ArtifactRefModel):
    """Select the exact JSON source supplying the withheld observations."""

    media_type: Literal["application/json"] = "application/json"
    manifest_profile_sha256: str = Field(pattern=_SELECTED_SHA256)


class BacktestPoolingPolicyRef(ArtifactRefModel):
    """Exact pre-execution selection of historical comparison policy."""

    kind: Literal["ir.backtest_pooling_policy"] = "ir.backtest_pooling_policy"
    media_type: Literal["application/json"] = "application/json"
    manifest_profile_sha256: str = Field(pattern=_SELECTED_SHA256)


class BacktestPoolingMember(BaseModel):
    """One selected source window of a semantic scenario and its provided forecast."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: str = Field(min_length=1, strict=True)
    metric_name: str = Field(min_length=1, strict=True)
    scenario_group: str = Field(min_length=1, strict=True)
    macro_weight: Decimal = Field(gt=0, allow_inf_nan=False)
    historical_rows_ref: SelectedHistoricalRowsRef
    observation_start: int = Field(ge=0, strict=True)
    predictions: tuple[Annotated[float, Field(strict=True, allow_inf_nan=False)], ...] = Field(
        min_length=1
    )
    comparison_representation_ref: SelectedRepresentationRef | None = None
    canonical_representation_ref: SelectedRepresentationRef | None = None

    @model_validator(mode="after")
    def _validate_declared_measure(self) -> BacktestPoolingMember:
        if (self.comparison_representation_ref is None) != (
            self.canonical_representation_ref is None
        ):
            raise ValueError("backtest pooling requires both representations or declared unknown")
        return self


class BacktestPoolingPolicy(BaseModel):
    """Fix member windows, quantities and macro weights before the backtest runs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    members: tuple[BacktestPoolingMember, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_groups(self) -> BacktestPoolingPolicy:
        if len({member.scenario_id for member in self.members}) != len(self.members):
            raise ValueError("backtest pooling scenario IDs must be unique")
        groups: dict[str, list[BacktestPoolingMember]] = defaultdict(list)
        for member in self.members:
            groups[member.scenario_group].append(member)
        for members in groups.values():
            lead = members[0]
            windows: list[tuple[int, int]] = []
            for member in members:
                if (
                    member.metric_name != lead.metric_name
                    or member.macro_weight != lead.macro_weight
                    or member.historical_rows_ref != lead.historical_rows_ref
                    or member.comparison_representation_ref != lead.comparison_representation_ref
                    or member.canonical_representation_ref != lead.canonical_representation_ref
                ):
                    raise ValueError("backtest shards disagree on their semantic scenario")
                windows.append(
                    (
                        member.observation_start,
                        member.observation_start + len(member.predictions),
                    )
                )
            windows.sort()
            if any(previous[1] > current[0] for previous, current in pairwise(windows)):
                raise ValueError("backtest shards overlap in their selected source observations")
        return self


class BacktestFixedUnitTransform(BaseModel):
    """The actual Fabric factor and definition fingerprints used on both operands."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_unit: str = Field(min_length=1, strict=True)
    canonical_unit: str = Field(min_length=1, strict=True)
    multiplier: Decimal = Field(gt=0, allow_inf_nan=False)
    definition_basis_content_sha256: str = Field(pattern=_SELECTED_SHA256)
    definition_content_sha256: str = Field(pattern=_SELECTED_SHA256)
    transform_ref: Literal["fabric://units/fixed-multiplicative/v1"]
    executor_version: Literal["polisyos.fabric.units.fixed-multiplicative.v1"]


class BacktestPoolingMeasure(BaseModel):
    """A preflight qualification, tied by position to the selected member."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    semantic_definition_ref: SelectedDefinitionRef | None = None
    canonical_unit: str | None = Field(default=None, min_length=1, strict=True)
    transform: BacktestFixedUnitTransform | None = None
    limitation: str | None = Field(default=None, min_length=1, strict=True)

    @model_validator(mode="after")
    def _validate_status(self) -> BacktestPoolingMeasure:
        if (self.canonical_unit is None) != (self.limitation is not None):
            raise ValueError("backtest measure requires a canonical unit or a limitation")
        if (self.semantic_definition_ref is None) != (self.canonical_unit is None):
            raise ValueError("backtest measure requires the exact semantic definition")
        if self.transform is not None and self.transform.canonical_unit != self.canonical_unit:
            raise ValueError("backtest unit conversion is outside its selected measure")
        return self


class BacktestPooledStratum(BaseModel):
    """Numerical summary in exactly one selected measurement representation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    representation_ref: SelectedRepresentationRef
    semantic_definition_ref: SelectedDefinitionRef
    canonical_unit: str = Field(min_length=1)
    scenario_ids: tuple[str, ...] = Field(min_length=1)
    comparison_count: int = Field(gt=0)
    micro_rmse: float = Field(ge=0.0, allow_inf_nan=False)
    micro_mae: float = Field(ge=0.0, allow_inf_nan=False)
    weighted_macro_rmse: float = Field(ge=0.0, allow_inf_nan=False)


class BacktestPoolingProjection(BaseModel):
    """Selected normalized statistics with explicit nonpooled source members."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_ref: BacktestPoolingPolicyRef
    measures: tuple[BacktestPoolingMeasure, ...] = Field(min_length=1)
    strata: tuple[BacktestPooledStratum, ...]
    unavailable: dict[str, str]

    @property
    def combined_stratum(self) -> BacktestPooledStratum | None:
        """Expose a cohort-wide RMSE only when all members share one measure."""
        return self.strata[0] if len(self.strata) == 1 and not self.unavailable else None


_POLICY_OWNER = declare_model_owner(
    BacktestPoolingPolicy,
    contract_id="ir.analytics.backtest_pooling_policy.owner.v1",
    dto_fqn="polisyos.ir.analytics.backtest_pooling.BacktestPoolingPolicy",
    abi_key="ir.analytics.backtest_pooling_policy.owner.v1.dto-abi.v1",
    registry_key=_POLICY_KIND,
    kind=_POLICY_KIND,
    media_type="application/json",
    purpose="backtest_pooling_policy",
    policy_revision="ir.analytics.backtest_pooling_policy.owner.v1.admission.v1",
    accepted_wire_policies=(("ir.analytics.backtest_pooling_policy.wire-law", "1"),),
    payload_version_field="schema_version",
    validate_profile=owner_profile_for_spec(_CANON, profile_ref=None),
    representations=(
        OwnedJSONRepresentation(
            schema_name=_POLICY_KIND,
            schema_version="1.0",
            payload_version="1.0",
            wire_policy_ref="ir.analytics.backtest_pooling_policy.wire-law",
            wire_policy_revision="1",
            profile_ref=None,
            compatibility=CompatibilityMode.NONE,
            notes=("Preselected measurements and scenario weights for candidate arithmetic.",),
            readable=True,
            writable=True,
            current=True,
            default_write=True,
            readable_from=(),
        ),
    ),
)


def _selected_input(ref: ArtifactRefModel, role: str) -> InputRef:
    return InputRef(
        artifact_id=ref.artifact_id,
        role=role,
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )


def _pooling_policy_inputs(policy: BacktestPoolingPolicy) -> list[InputRef]:
    inputs: list[InputRef] = []
    for member in policy.members:
        inputs.append(_selected_input(member.historical_rows_ref, f"source:{member.scenario_id}"))
        source = member.comparison_representation_ref
        target = member.canonical_representation_ref
        if source is not None and target is not None:
            inputs.extend(
                (
                    _selected_input(source, f"measurement:{member.scenario_id}"),
                    _selected_input(target, f"canonical_measurement:{member.scenario_id}"),
                )
            )
    return inputs


def read_selected_inputs(store: ArtifactStore, selector: ArtifactRefModel) -> list[InputRef]:
    """Reopen lineage from an exact selected artifact manifest."""
    manifest = store.get_manifest(selector)
    raw = (
        manifest.get("inputs")
        if isinstance(manifest, Mapping)
        else getattr(manifest, "inputs", None)
    )
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        raise ValueError("backtest pooling manifest inputs are unavailable")
    return [InputRef.model_validate(edge, from_attributes=True) for edge in raw]


def pooling_policy_edge(ref: BacktestPoolingPolicyRef) -> InputRef:
    """Return the selected report's dedicated policy input edge."""
    return _selected_input(ref, _POLICY_ROLE)


def verify_pooling_policy_edge(
    inputs: Sequence[InputRef],
    projection: BacktestPoolingProjection | None,
) -> None:
    """Require a unique body-to-manifest policy binding, including removal controls."""
    selected = [edge for edge in inputs if edge.role == _POLICY_ROLE]
    expected = [] if projection is None else [pooling_policy_edge(projection.policy_ref)]
    if selected != expected:
        raise ValueError("backtest pooling policy manifest binding differs")


def persist_backtest_pooling_policy(
    store: ArtifactStore, policy: BacktestPoolingPolicy
) -> BacktestPoolingPolicyRef:
    """Persist a policy and the exact selected inputs before evaluation."""
    verified = BacktestPoolingPolicy.model_validate(policy.model_dump(mode="python"))
    ref = _put_owned_json_artifact(
        store,
        verified.model_dump(mode="json"),
        owner=_POLICY_OWNER,
        schema_name=_POLICY_KIND,
        schema_version="1.0",
        inputs=_pooling_policy_inputs(verified),
        canon_spec=_CANON,
    )
    return BacktestPoolingPolicyRef.model_validate(ref)


def load_backtest_pooling_policy(
    store: ArtifactStore, ref: BacktestPoolingPolicyRef
) -> BacktestPoolingPolicy:
    """Reopen the selected typed policy and reconcile every source/measurement edge."""
    policy = _get_owned_json_artifact(store, ref, owner=_POLICY_OWNER)
    observed = read_selected_inputs(store, ref)
    expected = _pooling_policy_inputs(policy)
    if len(observed) != len(expected) or {edge.role: edge for edge in observed} != {
        edge.role: edge for edge in expected
    }:
        raise ValueError("backtest pooling policy inputs differ from the selected manifest")
    return policy


def _converted_residual(predicted: float, observed: float, scale: Fraction) -> float:
    """Normalize both source operands exactly before rounding the residual once."""
    residual = Fraction(predicted) * scale - Fraction(observed) * scale
    rounded = float(residual)
    if rounded == 0.0 and residual:
        raise OverflowError("normalized backtest residual underflow")
    return rounded


def project_backtest_pooling(
    policy_ref: BacktestPoolingPolicyRef,
    policy: BacktestPoolingPolicy,
    measures: tuple[BacktestPoolingMeasure, ...],
    scenarios: Sequence[BacktestScenario],
    summarize_errors: Callable[[list[float], tuple[()]], _BacktestErrorSummary],
) -> BacktestPoolingProjection:
    """Recompute candidate statistics from selected source rows and applied factors."""
    by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    if len(by_id) != len(scenarios) or set(by_id) != {
        member.scenario_id for member in policy.members
    }:
        raise ValueError("backtest pooling policy and examined scenarios differ")
    strata: dict[
        tuple[str, str], list[tuple[BacktestPoolingMember, BacktestPoolingMeasure, list[float]]]
    ]
    strata = defaultdict(list)
    unavailable: dict[str, str] = {}
    for member, measure in zip(policy.members, measures, strict=True):
        scenario = by_id[member.scenario_id]
        rows = scenario.outcome_comparisons
        if measure.limitation is not None:
            unavailable[member.scenario_id] = measure.limitation
            continue
        if scenario.requested_count != len(member.predictions) or len(rows) != len(
            member.predictions
        ):
            unavailable[member.scenario_id] = "selected_rows_incomplete"
            continue
        if (
            any(row.metric_name != member.metric_name for row in rows)
            or tuple(row.y_pred for row in rows) != member.predictions
        ):
            raise ValueError("backtest pooling rows differ from the selected prediction")
        canonical = member.canonical_representation_ref
        if canonical is None:
            raise ValueError("backtest pooling resolved an undeclared representation")
        multiplier = Fraction(measure.transform.multiplier) if measure.transform else Fraction(1)
        try:
            residuals = [_converted_residual(row.y_pred, row.y_true, multiplier) for row in rows]
        except OverflowError:
            residuals = []
        if not residuals or not all(math.isfinite(value) for value in residuals):
            unavailable[member.scenario_id] = "normalized_residual_not_representable"
            continue
        strata[(str(canonical.artifact_id), canonical.manifest_profile_sha256)].append(
            (member, measure, residuals)
        )

    incomplete_groups = {
        member.scenario_group for member in policy.members if member.scenario_id in unavailable
    }
    summaries: list[BacktestPooledStratum] = []
    for blocks in strata.values():
        complete = []
        for member, measure, residuals in blocks:
            if member.scenario_group in incomplete_groups:
                unavailable[member.scenario_id] = "semantic_scenario_incomplete"
            else:
                complete.append((member, measure, residuals))
        if not complete:
            continue
        groups: dict[str, list[float]] = defaultdict(list)
        weights: dict[str, Fraction] = {}
        for member, _, residuals in complete:
            groups[member.scenario_group].extend(residuals)
            weights[member.scenario_group] = Fraction(member.macro_weight)
        residuals = [residual for _, _, block in complete for residual in block]
        total = summarize_errors(residuals, ())
        weighted = Fraction(0)
        for group, group_residuals in groups.items():
            error = summarize_errors(group_residuals, ()).rmse
            if error is None:
                raise ValueError("backtest pooled group lacks comparisons")
            weighted += Fraction(error) * weights[group]
        canonical = complete[0][0].canonical_representation_ref
        unit = complete[0][1].canonical_unit
        definition = complete[0][1].semantic_definition_ref
        if (
            canonical is None
            or unit is None
            or definition is None
            or any(
                measure.canonical_unit != unit or measure.semantic_definition_ref != definition
                for _, measure, _ in complete
            )
        ):
            raise ValueError("backtest pooled stratum disagrees on its canonical measure")
        if total.rmse is None or total.mae is None:
            raise ValueError("backtest pooled stratum lacks comparisons")
        summaries.append(
            BacktestPooledStratum(
                representation_ref=canonical,
                semantic_definition_ref=definition,
                canonical_unit=unit,
                scenario_ids=tuple(member.scenario_id for member, _, _ in complete),
                comparison_count=len(residuals),
                micro_rmse=total.rmse,
                micro_mae=total.mae,
                weighted_macro_rmse=float(weighted / sum(weights.values())),
            )
        )
    return BacktestPoolingProjection(
        policy_ref=policy_ref,
        measures=measures,
        strata=tuple(summaries),
        unavailable=unavailable,
    )
