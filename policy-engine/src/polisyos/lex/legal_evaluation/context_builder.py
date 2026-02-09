from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import Metrics, SimulationResult
from polisyos.core.contracts.lex import LegalEvaluationRequest
from polisyos.core.contracts.trinity import PolicySpecRef
from polisyos.ir.norm_pack import NormPack, NormRule
from polisyos.ir.governance.policy_spec import ParameterSpec, PolicySpec
from polisyos.lex.common import collapse_ws
from polisyos.lex.errors import LexNotReadyError, LexValidationError
from polisyos.lex.normpack.applicability import applies_to_context


def _decimal_from_string(value: str) -> Decimal | None:
    raw = value.strip()
    if not raw:
        return None
    try:
        parsed = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite():
        return None
    return parsed


def _decimal_to_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _json_pointer_escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


@dataclass(frozen=True)
class ObservedValue:
    predicate_id: str
    source_kind: str
    value_kind: str
    value_text: str
    value_decimal: str | None
    unit_id: str | None
    simulation_result_ref: str | None
    metrics_ref: str | None
    metric_key: str | None
    policy_spec_ref: str | None
    policy_json_pointer: str | None


@dataclass(frozen=True)
class RuleObservation:
    rule_id: str
    predicate_id: str
    applies: bool
    observed: ObservedValue | None
    mapping_notes: list[str]


@dataclass(frozen=True)
class LegalContext:
    request: LegalEvaluationRequest
    jurisdiction_norm: str
    as_of_norm: str
    policy: PolicySpec
    norm_pack: NormPack
    simulation_result: SimulationResult
    metrics: Metrics | None
    observations_by_rule_id: dict[str, RuleObservation]
    quality_issues: list[dict[str, Any]]
    artifacts_used: list[str]


def _load_model_from_cas(
    *,
    cas: FileSystemCAS,
    artifact_id: str,
    model: type[PolicySpec] | type[SimulationResult] | type[Metrics] | type[NormPack],
    role: str,
) -> PolicySpec | SimulationResult | Metrics | NormPack:
    try:
        payload = from_canonical_bytes(cas.get_bytes(ArtifactID.model_validate(artifact_id)))
    except FileNotFoundError as exc:
        raise LexNotReadyError(
            f"missing required artifact for {role}: {artifact_id}",
            details={"role": role, "artifact_id": artifact_id},
        ) from exc
    except Exception as exc:
        raise LexValidationError(
            f"failed to decode artifact for {role}: {artifact_id}",
            details={"role": role, "artifact_id": artifact_id},
        ) from exc

    try:
        return model.model_validate(payload)
    except Exception as exc:
        raise LexValidationError(
            f"invalid payload for {role}: {artifact_id}",
            details={"role": role, "artifact_id": artifact_id},
        ) from exc


def _observed_from_metric(
    *,
    predicate_id: str,
    raw: int | str,
    simulation_result_ref: str,
    metrics_ref: str,
) -> ObservedValue:
    if isinstance(raw, bool):
        value_text = "true" if raw else "false"
        return ObservedValue(
            predicate_id=predicate_id,
            source_kind="metrics",
            value_kind="boolean",
            value_text=value_text,
            value_decimal=None,
            unit_id=None,
            simulation_result_ref=simulation_result_ref,
            metrics_ref=metrics_ref,
            metric_key=predicate_id,
            policy_spec_ref=None,
            policy_json_pointer=None,
        )

    if isinstance(raw, int):
        value_decimal = str(raw)
        return ObservedValue(
            predicate_id=predicate_id,
            source_kind="metrics",
            value_kind="numeric",
            value_text=value_decimal,
            value_decimal=value_decimal,
            unit_id=None,
            simulation_result_ref=simulation_result_ref,
            metrics_ref=metrics_ref,
            metric_key=predicate_id,
            policy_spec_ref=None,
            policy_json_pointer=None,
        )

    stripped = collapse_ws(raw)
    parsed = _decimal_from_string(stripped)
    if parsed is not None:
        value_decimal = _decimal_to_text(parsed)
        return ObservedValue(
            predicate_id=predicate_id,
            source_kind="metrics",
            value_kind="numeric",
            value_text=value_decimal,
            value_decimal=value_decimal,
            unit_id=None,
            simulation_result_ref=simulation_result_ref,
            metrics_ref=metrics_ref,
            metric_key=predicate_id,
            policy_spec_ref=None,
            policy_json_pointer=None,
        )
    return ObservedValue(
        predicate_id=predicate_id,
        source_kind="metrics",
        value_kind="text",
        value_text=stripped,
        value_decimal=None,
        unit_id=None,
        simulation_result_ref=simulation_result_ref,
        metrics_ref=metrics_ref,
        metric_key=predicate_id,
        policy_spec_ref=None,
        policy_json_pointer=None,
    )


def _parse_policy_value(
    *,
    predicate_id: str,
    value: Any,
    policy_spec_ref: PolicySpecRef,
    json_pointer: str,
) -> tuple[ObservedValue | None, dict[str, Any] | None]:
    if isinstance(value, bool):
        value_text = "true" if value else "false"
        return (
            ObservedValue(
                predicate_id=predicate_id,
                source_kind="policy_param",
                value_kind="boolean",
                value_text=value_text,
                value_decimal=None,
                unit_id=None,
                simulation_result_ref=None,
                metrics_ref=None,
                metric_key=None,
                policy_spec_ref=str(policy_spec_ref.artifact_id),
                policy_json_pointer=json_pointer,
            ),
            None,
        )

    if isinstance(value, int):
        value_decimal = str(value)
        return (
            ObservedValue(
                predicate_id=predicate_id,
                source_kind="policy_param",
                value_kind="numeric",
                value_text=value_decimal,
                value_decimal=value_decimal,
                unit_id=None,
                simulation_result_ref=None,
                metrics_ref=None,
                metric_key=None,
                policy_spec_ref=str(policy_spec_ref.artifact_id),
                policy_json_pointer=json_pointer,
            ),
            None,
        )

    if isinstance(value, str):
        stripped = collapse_ws(value)
        parsed = _decimal_from_string(stripped)
        if parsed is not None:
            value_decimal = _decimal_to_text(parsed)
            return (
                ObservedValue(
                    predicate_id=predicate_id,
                    source_kind="policy_param",
                    value_kind="numeric",
                    value_text=value_decimal,
                    value_decimal=value_decimal,
                    unit_id=None,
                    simulation_result_ref=None,
                    metrics_ref=None,
                    metric_key=None,
                    policy_spec_ref=str(policy_spec_ref.artifact_id),
                    policy_json_pointer=json_pointer,
                ),
                None,
            )
        return (
            ObservedValue(
                predicate_id=predicate_id,
                source_kind="policy_param",
                value_kind="text",
                value_text=stripped,
                value_decimal=None,
                unit_id=None,
                simulation_result_ref=None,
                metrics_ref=None,
                metric_key=None,
                policy_spec_ref=str(policy_spec_ref.artifact_id),
                policy_json_pointer=json_pointer,
            ),
            None,
        )

    if isinstance(value, (dict, BaseModel)):
        return None, {
            "code": "unsupported_policy_value_type",
            "details": {"predicate_id": predicate_id, "python_type": type(value).__name__},
        }

    return None, {
        "code": "unsupported_policy_value_type",
        "details": {"predicate_id": predicate_id, "python_type": type(value).__name__},
    }


def _resolve_dot_path(params: dict[str, Any], path: str) -> tuple[Any, list[str], bool]:
    parts = [part for part in path.split(".") if part]
    if not parts:
        return None, [], False
    current: Any = params
    for part in parts:
        if not isinstance(current, dict):
            return None, parts, False
        if part not in current:
            return None, parts, False
        current = current[part]
    return current, parts, True


@dataclass(frozen=True)
class _InterventionRecord:
    index: int
    intervention_id: str
    params: dict[str, Any]


class LegalContextBuilder:
    def __init__(
        self,
        *,
        cas: FileSystemCAS,
        request: LegalEvaluationRequest,
        jurisdiction_norm: str,
        as_of_norm: str,
        policy_spec_ref: PolicySpecRef,
    ) -> None:
        self._cas = cas
        self._request = request
        self._jurisdiction_norm = jurisdiction_norm
        self._as_of_norm = as_of_norm
        self._policy_spec_ref = policy_spec_ref

    def build(self) -> LegalContext:
        policy = _load_model_from_cas(
            cas=self._cas,
            artifact_id=str(self._policy_spec_ref.artifact_id),
            model=PolicySpec,
            role="policy_spec",
        )
        simulation_result = _load_model_from_cas(
            cas=self._cas,
            artifact_id=str(self._request.simulation_result_ref.artifact_id),
            model=SimulationResult,
            role="simulation_result",
        )
        metrics = _load_model_from_cas(
            cas=self._cas,
            artifact_id=str(simulation_result.metrics_ref.artifact_id),
            model=Metrics,
            role="metrics",
        )
        norm_pack = _load_model_from_cas(
            cas=self._cas,
            artifact_id=str(self._request.norm_pack_ref.artifact_id),
            model=NormPack,
            role="norm_pack",
        )

        observations_by_rule_id: dict[str, RuleObservation] = {}
        quality_issues: list[dict[str, Any]] = []

        interventions: list[_InterventionRecord] = [
            _InterventionRecord(
                index=index,
                intervention_id=intervention.intervention_id,
                params=dict(intervention.params),
            )
            for index, intervention in enumerate(policy.interventions)
        ]
        intervention_by_id = {row.intervention_id: row for row in interventions}
        parameter_by_id: dict[str, ParameterSpec] = {
            parameter.param_id: parameter for parameter in policy.parameters
        }

        for rule in sorted(norm_pack.norms, key=lambda row: row.norm_id):
            observation, rule_issues = self._build_rule_observation(
                rule=rule,
                simulation_result=simulation_result,
                metrics=metrics,
                interventions=interventions,
                intervention_by_id=intervention_by_id,
                parameter_by_id=parameter_by_id,
            )
            observations_by_rule_id[observation.rule_id] = observation
            quality_issues.extend(rule_issues)

        quality_issues.sort(
            key=lambda issue: (
                str(issue.get("rule_id", "")),
                str(issue.get("code", "")),
                str(issue.get("details", "")),
            )
        )

        artifacts_used = [
            str(self._policy_spec_ref.artifact_id),
            str(self._request.simulation_result_ref.artifact_id),
            str(simulation_result.metrics_ref.artifact_id),
            str(self._request.norm_pack_ref.artifact_id),
        ]
        return LegalContext(
            request=self._request,
            jurisdiction_norm=self._jurisdiction_norm,
            as_of_norm=self._as_of_norm,
            policy=policy,
            norm_pack=norm_pack,
            simulation_result=simulation_result,
            metrics=metrics,
            observations_by_rule_id=observations_by_rule_id,
            quality_issues=quality_issues,
            artifacts_used=artifacts_used,
        )

    def _build_rule_observation(
        self,
        *,
        rule: NormRule,
        simulation_result: SimulationResult,
        metrics: Metrics | None,
        interventions: list[_InterventionRecord],
        intervention_by_id: dict[str, _InterventionRecord],
        parameter_by_id: dict[str, ParameterSpec],
    ) -> tuple[RuleObservation, list[dict[str, Any]]]:
        metadata = dict(rule.backend_metadata or {})
        predicate_id = metadata.get("predicate_id")
        if not isinstance(predicate_id, str):
            predicate_id = ""

        applies = applies_to_context(
            applicability=rule.applicability,
            jurisdiction_norm=self._jurisdiction_norm,
            as_of_iso=self._as_of_norm,
        )
        if not applies:
            return (
                RuleObservation(
                    rule_id=rule.norm_id,
                    predicate_id=predicate_id,
                    applies=False,
                    observed=None,
                    mapping_notes=["not_applicable"],
                ),
                [],
            )

        observed, mapping_notes, issues = self._map_observed_value(
            rule=rule,
            predicate_id=predicate_id,
            simulation_result=simulation_result,
            metrics=metrics,
            interventions=interventions,
            intervention_by_id=intervention_by_id,
            parameter_by_id=parameter_by_id,
        )
        return (
            RuleObservation(
                rule_id=rule.norm_id,
                predicate_id=predicate_id,
                applies=True,
                observed=observed,
                mapping_notes=mapping_notes,
            ),
            issues,
        )

    def _map_observed_value(
        self,
        *,
        rule: NormRule,
        predicate_id: str,
        simulation_result: SimulationResult,
        metrics: Metrics | None,
        interventions: list[_InterventionRecord],
        intervention_by_id: dict[str, _InterventionRecord],
        parameter_by_id: dict[str, ParameterSpec],
    ) -> tuple[ObservedValue | None, list[str], list[dict[str, Any]]]:
        notes: list[str] = []
        issues: list[dict[str, Any]] = []

        if predicate_id and metrics is not None and predicate_id in metrics.values:
            observed = _observed_from_metric(
                predicate_id=predicate_id,
                raw=metrics.values[predicate_id],
                simulation_result_ref=str(self._request.simulation_result_ref.artifact_id),
                metrics_ref=str(simulation_result.metrics_ref.artifact_id),
            )
            notes.append("mapping=metrics")
            return observed, notes, issues

        parameter = parameter_by_id.get(predicate_id)
        if parameter is not None:
            intervention = intervention_by_id.get(parameter.intervention_id)
            if intervention is not None:
                value, parts, ok = _resolve_dot_path(intervention.params, parameter.param_path)
                if ok:
                    pointer = "/interventions/{idx}/params/{suffix}".format(
                        idx=intervention.index,
                        suffix="/".join(_json_pointer_escape(part) for part in parts),
                    )
                    observed, issue = _parse_policy_value(
                        predicate_id=predicate_id,
                        value=value,
                        policy_spec_ref=self._policy_spec_ref,
                        json_pointer=pointer,
                    )
                    notes.append("mapping=policy_param:parameter_spec")
                    if issue is not None:
                        issue["code"] = str(issue["code"])
                        issue["rule_id"] = rule.norm_id
                        issues.append(issue)
                        return None, notes, issues
                    if observed is not None:
                        return observed, notes, issues
                else:
                    issues.append(
                        {
                            "code": "missing_observed_value",
                            "rule_id": rule.norm_id,
                            "details": {
                                "predicate_id": predicate_id,
                                "reason": "parameter_path_not_found",
                                "intervention_id": parameter.intervention_id,
                                "param_path": parameter.param_path,
                            },
                        }
                    )
                    notes.append("mapping=policy_param:parameter_path_not_found")
                    return None, notes, issues
            else:
                issues.append(
                    {
                        "code": "missing_observed_value",
                        "rule_id": rule.norm_id,
                        "details": {
                            "predicate_id": predicate_id,
                            "reason": "intervention_not_found",
                            "intervention_id": parameter.intervention_id,
                        },
                    }
                )
                notes.append("mapping=policy_param:intervention_not_found")
                return None, notes, issues

        direct_matches: list[tuple[int, str, Any]] = []
        for intervention in interventions:
            if predicate_id in intervention.params:
                direct_matches.append(
                    (
                        intervention.index,
                        intervention.intervention_id,
                        intervention.params[predicate_id],
                    )
                )

        if len(direct_matches) == 1:
            index, _, value = direct_matches[0]
            pointer = f"/interventions/{index}/params/{_json_pointer_escape(predicate_id)}"
            observed, issue = _parse_policy_value(
                predicate_id=predicate_id,
                value=value,
                policy_spec_ref=self._policy_spec_ref,
                json_pointer=pointer,
            )
            notes.append("mapping=policy_param:direct_key")
            if issue is not None:
                issue["code"] = str(issue["code"])
                issue["rule_id"] = rule.norm_id
                issues.append(issue)
                return None, notes, issues
            if observed is not None:
                return observed, notes, issues

        if len(direct_matches) > 1:
            issues.append(
                {
                    "code": "ambiguous_policy_mapping",
                    "rule_id": rule.norm_id,
                    "details": {
                        "predicate_id": predicate_id,
                        "intervention_ids": sorted({row[1] for row in direct_matches}),
                    },
                }
            )
            notes.append("mapping=policy_param:ambiguous")
            return None, notes, issues

        issues.append(
            {
                "code": "missing_observed_value",
                "rule_id": rule.norm_id,
                "details": {"predicate_id": predicate_id},
            }
        )
        notes.append("mapping=none")
        return None, notes, issues


__all__ = [
    "LegalContext",
    "LegalContextBuilder",
    "ObservedValue",
    "RuleObservation",
]
