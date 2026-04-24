from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    Metrics,
    MetricsRef,
    SimulationResult,
    SimulationResultRef,
)
from polisyos.core.contracts.lex import LegalEvaluationRequest
from polisyos.core.contracts.trinity import PolicySpecRef
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.world.materialize import materialize_world_duckdb_from_fact_log
from polisyos.ir.citations import CitationRef, DocumentRef
from polisyos.ir.governance.policy_spec import InterventionSpec, ParameterSpec, PolicySpec
from polisyos.ir.norm_pack import NormPack, NormRef, NormRule, RuleType
from polisyos.ir.types import SelectorOperator
from polisyos.lex.api import evaluate_legality
from polisyos.lex.legal_evaluation.backends.simple_v1 import evaluate_rule_simple_v1
from polisyos.lex.legal_evaluation.context_builder import (
    LegalContextBuilder,
    ObservedValue,
    RuleObservation,
)


def _citation(fragment_id: str) -> CitationRef:
    return CitationRef(
        doc=DocumentRef(doc_id="doc.test", doc_version_id="docv.test"),
        fragment_id=fragment_id,
    )


def _rule(
    *,
    rule_id: str,
    predicate_id: str,
    operator: str | None,
    value_decimal: str | None,
    value_text: str,
) -> NormRule:
    backend_metadata = {
        "predicate_id": predicate_id,
        "operator": operator,
        "value_decimal": value_decimal,
        "value_text": value_text,
        "unit_id": None,
    }
    return NormRule(
        norm_id=rule_id,
        provision_refs=[
            NormRef(
                provision_id=f"frag.{rule_id}",
                citations=[_citation(fragment_id=f"frag.{rule_id}")],
            )
        ],
        rule_type=RuleType.OBLIGATION,
        description=rule_id,
        backend_metadata=backend_metadata,
    )


def _observed_numeric(*, rule_id: str, predicate_id: str, value: str) -> RuleObservation:
    return RuleObservation(
        rule_id=rule_id,
        predicate_id=predicate_id,
        applies=True,
        observed=ObservedValue(
            predicate_id=predicate_id,
            source_kind="metrics",
            value_kind="numeric",
            value_text=value,
            value_decimal=value,
            unit_id=None,
            simulation_result_ref="sha256:" + "1" * 64,
            metrics_ref="sha256:" + "2" * 64,
            metric_key=predicate_id,
            policy_spec_ref=None,
            policy_json_pointer=None,
        ),
        mapping_notes=["mapping=metrics"],
    )


@pytest.mark.parametrize(
    ("operator", "observed", "expected", "expected_status"),
    [
        ("<", "4", "5", "PASS"),
        ("<=", "5", "5", "PASS"),
        ("=", "5", "5", "PASS"),
        (">=", "6", "5", "PASS"),
        (">", "6", "5", "PASS"),
        ("<", "6", "5", "FAIL"),
        ("<=", "6", "5", "FAIL"),
        ("=", "6", "5", "FAIL"),
        (">=", "4", "5", "FAIL"),
        (">", "4", "5", "FAIL"),
    ],
)
def test_simple_v1_numeric_operators(
    operator: str,
    observed: str,
    expected: str,
    expected_status: str,
) -> None:
    rule = _rule(
        rule_id="claim.numeric",
        predicate_id="kpi.numeric",
        operator=operator,
        value_decimal=expected,
        value_text=expected,
    )
    observation = _observed_numeric(
        rule_id=rule.norm_id,
        predicate_id="kpi.numeric",
        value=observed,
    )
    finding, issues = evaluate_rule_simple_v1(rule=rule, observation=observation, strict=True)
    assert finding.status == expected_status
    assert issues == []


def test_simple_v1_unknown_when_missing_operator_or_value() -> None:
    no_operator_rule = _rule(
        rule_id="claim.no_operator",
        predicate_id="kpi.numeric",
        operator=None,
        value_decimal="10",
        value_text="10",
    )
    missing_value_rule = _rule(
        rule_id="claim.no_value",
        predicate_id="kpi.numeric",
        operator="<=",
        value_decimal=None,
        value_text="",
    )
    observation = _observed_numeric(
        rule_id="claim.no_operator",
        predicate_id="kpi.numeric",
        value="7",
    )

    finding_no_operator, issues_no_operator = evaluate_rule_simple_v1(
        rule=no_operator_rule,
        observation=observation,
        strict=False,
    )
    finding_no_value, issues_no_value = evaluate_rule_simple_v1(
        rule=missing_value_rule,
        observation=observation,
        strict=False,
    )

    assert finding_no_operator.status == "UNKNOWN"
    assert finding_no_value.status == "UNKNOWN"
    assert any(issue["code"] == "missing_operator" for issue in issues_no_operator)
    assert any(issue["code"] == "missing_expected_value" for issue in issues_no_value)


def _policy_with_mapping_cases() -> PolicySpec:
    return PolicySpec(
        policy_id="policy_legal_eval",
        interventions=[
            InterventionSpec(
                intervention_id="int_0",
                kind="income_tax",
                target={
                    "kind": "predicate",
                    "field": "id",
                    "operator": SelectorOperator.EQUALS,
                    "value": "all",
                },
                schedule={"start_step": 0, "duration_steps": 1},
                params={"speed_limit": "70", "dup_metric": "1"},
            ),
            InterventionSpec(
                intervention_id="int_1",
                kind="income_tax",
                target={
                    "kind": "predicate",
                    "field": "id",
                    "operator": SelectorOperator.EQUALS,
                    "value": "all",
                },
                schedule={"start_step": 0, "duration_steps": 1},
                params={"dup_metric": "2"},
            ),
        ],
        parameters=[
            ParameterSpec(
                param_id="speed_limit",
                intervention_id="int_0",
                param_path="speed_limit",
                default_value="70",
            )
        ],
    )


def test_context_builder_mapping_metrics_policy_and_ambiguity(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")

    policy = _policy_with_mapping_cases()
    policy_ref_payload = cas.put_json(
        policy.model_dump(mode="python"),
        PutOptions(
            kind="ir.policy_spec",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.PolicySpec", version=policy.schema_version),
        ),
    )
    policy_ref = PolicySpecRef(artifact_id=policy_ref_payload.artifact_id)

    metrics = Metrics(values={"accident_rate": "0.03"})
    metrics_ref = cas.put_json(
        metrics.model_dump(mode="python"),
        PutOptions(
            kind="foundry.metrics",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.Metrics", version="1.0"),
        ),
    )
    simulation = SimulationResult(
        exec_plan_ref=ExecPlanRef(artifact_id="sha256:" + "9" * 64),
        metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
    )
    simulation_ref = cas.put_json(
        simulation.model_dump(mode="python"),
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.0"),
        ),
    )

    norm_pack = NormPack(
        pack_id="pack.mapping",
        jurisdiction="ua",
        effective_date="2026-02-04",
        norms=[
            _rule(
                rule_id="claim.metrics",
                predicate_id="accident_rate",
                operator="<=",
                value_decimal="0.05",
                value_text="0.05",
            ),
            _rule(
                rule_id="claim.policy",
                predicate_id="speed_limit",
                operator="<=",
                value_decimal="60",
                value_text="60",
            ),
            _rule(
                rule_id="claim.ambiguous",
                predicate_id="dup_metric",
                operator="<=",
                value_decimal="10",
                value_text="10",
            ),
        ],
    )
    norm_pack_ref = cas.put_json(
        norm_pack.model_dump(mode="python"),
        PutOptions(
            kind="lex.norm_pack",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.NormPack", version=norm_pack.schema_version),
        ),
    )

    request = LegalEvaluationRequest(
        jurisdiction="UA",
        as_of="2026-02-04",
        policy_spec_ref=policy_ref,
        simulation_result_ref=SimulationResultRef(artifact_id=simulation_ref.artifact_id),
        norm_pack_ref=norm_pack_ref,
        strict=True,
    )
    context = LegalContextBuilder(
        cas=cas,
        request=request,
        jurisdiction_norm="ua",
        as_of_norm="2026-02-04",
        policy_spec_ref=policy_ref,
    ).build()

    metrics_obs = context.observations_by_rule_id["claim.metrics"]
    policy_obs = context.observations_by_rule_id["claim.policy"]
    ambiguous_obs = context.observations_by_rule_id["claim.ambiguous"]

    assert metrics_obs.observed is not None
    assert metrics_obs.observed.source_kind == "metrics"
    assert metrics_obs.observed.metric_key == "accident_rate"

    assert policy_obs.observed is not None
    assert policy_obs.observed.source_kind == "policy_param"
    assert policy_obs.observed.policy_json_pointer == "/interventions/0/params/speed_limit"

    assert ambiguous_obs.observed is None
    assert any(
        issue["code"] == "ambiguous_policy_mapping" and issue["rule_id"] == "claim.ambiguous"
        for issue in context.quality_issues
    )


def _policy_for_e2e() -> PolicySpec:
    return PolicySpec(
        policy_id="policy_e2e",
        interventions=[
            InterventionSpec(
                intervention_id="speed_control",
                kind="income_tax",
                target={
                    "kind": "predicate",
                    "field": "id",
                    "operator": SelectorOperator.EQUALS,
                    "value": "all",
                },
                schedule={"start_step": 0, "duration_steps": 1},
                params={"speed_limit": "70"},
            )
        ],
        parameters=[
            ParameterSpec(
                param_id="speed_limit",
                intervention_id="speed_control",
                param_path="speed_limit",
                default_value="70",
            )
        ],
    )


def test_legal_evaluation_phase18_end_to_end(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))

    policy = _policy_for_e2e()
    policy_ref_payload = cas.put_json(
        policy.model_dump(mode="python"),
        PutOptions(
            kind="ir.policy_spec",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.PolicySpec", version=policy.schema_version),
        ),
    )
    policy_ref = PolicySpecRef(artifact_id=policy_ref_payload.artifact_id)

    metrics = Metrics(values={"accident_rate": "0.03"})
    metrics_ref = cas.put_json(
        metrics.model_dump(mode="python"),
        PutOptions(
            kind="foundry.metrics",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.Metrics", version="1.0"),
        ),
    )
    simulation = SimulationResult(
        exec_plan_ref=ExecPlanRef(artifact_id="sha256:" + "8" * 64),
        metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
    )
    simulation_ref_payload = cas.put_json(
        simulation.model_dump(mode="python"),
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.0"),
        ),
    )
    simulation_ref = SimulationResultRef(artifact_id=simulation_ref_payload.artifact_id)

    norm_pack = NormPack(
        pack_id="pack.e2e",
        jurisdiction="ua",
        effective_date="2026-02-04",
        norms=[
            _rule(
                rule_id="claim.accident_rate",
                predicate_id="accident_rate",
                operator="<=",
                value_decimal="0.05",
                value_text="0.05",
            ),
            _rule(
                rule_id="claim.speed_limit",
                predicate_id="speed_limit",
                operator="<=",
                value_decimal="60",
                value_text="60",
            ),
        ],
    )
    norm_pack_ref = cas.put_json(
        norm_pack.model_dump(mode="python"),
        PutOptions(
            kind="lex.norm_pack",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.NormPack", version=norm_pack.schema_version),
        ),
    )

    request = LegalEvaluationRequest(
        jurisdiction="UA",
        as_of="2026-02-04",
        policy_spec_ref=policy_ref,
        simulation_result_ref=simulation_ref,
        norm_pack_ref=norm_pack_ref,
        strict=True,
    )

    report_ref, proposal_refs = evaluate_legality(
        cas=cas,
        fact_log_root=tmp_path,
        request=request,
    )

    assert cas.has(report_ref.artifact_id)
    assert proposal_refs
    assert cas.has(proposal_refs[0].artifact_id)

    report_payload = from_canonical_bytes(cas.get_bytes(report_ref.artifact_id))
    proposal_payload = from_canonical_bytes(cas.get_bytes(proposal_refs[0].artifact_id))
    assert isinstance(report_payload, dict)
    assert isinstance(proposal_payload, dict)

    findings = report_payload.get("findings")
    assert isinstance(findings, list)
    speed_finding = next(row for row in findings if row["rule_id"] == "claim.speed_limit")
    assert speed_finding["status"] == "FAIL"
    assert speed_finding["norm_citations"][0]["provision_id"].startswith("frag.")

    actions = proposal_payload.get("actions")
    assert isinstance(actions, list) and actions
    policy_patch = next(row for row in actions if row["action_kind"] == "policy_patch")
    patch = policy_patch["patch_json"][0]
    assert patch["path"] == "/interventions/0/params/speed_limit"
    assert patch["value"] == "60"

    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)
    world_event_row = db.conn.execute(
        """
        SELECT event_kind, activity_id
        FROM world.world_events
        WHERE activity_id = 'prov.activity.lex_legal_eval.evaluate'
        ORDER BY started_at DESC
        LIMIT 1
        """
    ).fetchone()
    assert world_event_row == ("evaluate_legality", "prov.activity.lex_legal_eval.evaluate")
