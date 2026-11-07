from __future__ import annotations

import inspect
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.ir.analytics.frontier import (
    FrontierSketch,
    load_frontier_sketch,
    persist_frontier_sketch,
)
from polisyos.ir.artifacts.io import get_json_artifact, put_json_artifact
from polisyos.ir.migrations.base import (
    CompatibilityMode,
    get_ir_owner_registry_snapshot,
    get_schema_rule,
    register_ir_representation,
)
from polisyos.ir.model_layer.canon import CanonSpec, CanonViolation
from polisyos.ir.registry.refs import FrontierSketchRef

_OWNER_CASES = (
    (
        "dp_robustness",
        "_DP_ROBUSTNESS_OWNER",
        "DPRobustnessCertificate",
        "ir.dp_robustness_certificate",
        "ir.dp_robustness_certificate",
        "1.0",
        "1.0",
        "differential_privacy_robustness_evidence",
    ),
    (
        "dynamic_causal_semantics",
        "_FORECAST_INTERVENTION_QUERY_OWNER",
        "ForecastInterventionQuery",
        "ir.forecast_intervention_query",
        "ir.forecast_intervention_query",
        "1.0",
        "1.0",
        "forecast_intervention_query",
    ),
    (
        "dynamic_causal_semantics",
        "_FORECAST_INTERVENTION_CERTIFICATE_OWNER",
        "ForecastInterventionCertificate",
        "ir.forecast_intervention_certificate",
        "ir.forecast_intervention_certificate",
        "1.0",
        None,
        "forecast_intervention_certificate",
    ),
    (
        "dynamic_regime",
        "_CONTINUOUS_TIME_QUERY_OWNER",
        "ContinuousTimeQuery",
        "ir.continuous_time_query",
        "ir.continuous_time_query",
        "1.0",
        "1.0",
        "continuous_time_causal_query",
    ),
    (
        "dynamic_regime",
        "_TEMPORAL_INTERVENTION_TRAJECTORY_OWNER",
        "TemporalInterventionTrajectory",
        "ir.temporal_intervention_trajectory",
        "ir.temporal_intervention_trajectory",
        "1.0",
        "1.0",
        "temporal_intervention_trajectory",
    ),
    (
        "dynamic_regime",
        "_TEMPORAL_IDENTIFICATION_CERTIFICATE_OWNER",
        "TemporalIdentificationCertificate",
        "ir.temporal_identification_certificate",
        "ir.temporal_identification_certificate",
        "1.0",
        "1.0",
        "temporal_identification_certificate",
    ),
    (
        "dynamic_regime",
        "_DYNAMIC_TREATMENT_REGIME_OWNER",
        "DynamicTreatmentRegime",
        "ir.dynamic_treatment_regime",
        "ir.dynamic_treatment_regime",
        "1.1",
        "1.1",
        "dynamic_treatment_regime",
    ),
    (
        "dynamic_regime",
        "_EFFECT_TRAJECTORY_BUNDLE_OWNER",
        "EffectTrajectoryBundle",
        "ir.effect_trajectory_bundle",
        "ir.effect_trajectory_bundle",
        "1.0",
        "1.0",
        "effect_trajectory_bundle",
    ),
    (
        "endogenous_inequality",
        "_ENDOGENOUS_INEQUALITY_OWNER",
        "EndogenousGroupInequalityDecompositionResult",
        "ir.endogenous_group_inequality_decomposition",
        "ir.endogenous_group_inequality_decomposition",
        "1.0",
        "1.0",
        "endogenous_group_inequality_decomposition",
    ),
    (
        "estimand",
        "_ESTIMAND_AST_OWNER",
        "EstimandAST",
        "ir.estimand_ast",
        "ir.estimand_ast",
        "1.0",
        "1.0",
        "causal_estimand_ast",
    ),
    (
        "fairness_audit_report",
        "_FAIRNESS_AUDIT_REPORT_OWNER",
        "FairnessAuditReport",
        "polisyos.scientist.fairness_audit_report",
        "polisyos.scientist.fairness_audit_report",
        "1.0",
        "1.0.0",
        "fairness_audit_evidence",
    ),
    (
        "forecasting_uncertainty",
        "_FORECASTING_UNCERTAINTY_V1_OWNER",
        "ForecastingUncertaintyBundle",
        "ir.forecasting_uncertainty_bundle",
        "ir.forecasting_uncertainty_bundle",
        "1.0",
        "1.0",
        "forecasting_uncertainty_bundle",
    ),
    (
        "forecasting_uncertainty",
        "_FORECASTING_UNCERTAINTY_V2_OWNER",
        "ForecastingUncertaintyBundleV2",
        "ir.forecasting_uncertainty_bundle",
        "ir.forecasting_uncertainty_bundle",
        "2.0",
        "2.0",
        "forecasting_uncertainty_bundle",
    ),
    (
        "frontier",
        "_FRONTIER_SKETCH_OWNER",
        "FrontierSketch",
        "ir.frontier_sketch",
        "ir.frontier_sketch",
        "1.0",
        "1.0",
        "research_boundary_sketch",
    ),
)


@pytest.mark.parametrize(
    (
        "module_name",
        "owner_name",
        "model_name",
        "registry_key",
        "schema_name",
        "schema_version",
        "payload_version",
        "purpose",
    ),
    _OWNER_CASES,
)
def test_analytics_owner_registers_one_exact_profiled_wire_tuple(
    module_name: str,
    owner_name: str,
    model_name: str,
    registry_key: str,
    schema_name: str,
    schema_version: str,
    payload_version: str | None,
    purpose: str,
) -> None:
    module = import_module(f"polisyos.ir.analytics.{module_name}")
    owner = getattr(module, owner_name)
    model = getattr(module, model_name)
    snapshot = get_ir_owner_registry_snapshot()
    rows = tuple(
        row
        for row in snapshot.representations
        if row.registry_key == registry_key
        and row.owner_ref == owner.contract_id
        and row.schema_name == schema_name
    )

    dto_fqn = f"polisyos.ir.analytics.{module_name}.{model_name}"
    learned_regime = model_name == "DynamicTreatmentRegime"
    wire_policy = (f"{dto_fqn}.wire", "2" if learned_regime else "1")
    assert model.__module__ == f"polisyos.ir.analytics.{module_name}"
    assert owner.dto_fqn == dto_fqn
    assert owner.registry_key == registry_key
    assert owner.purpose == purpose
    if learned_regime:
        assert owner.accepted_wire_policies == ((f"{dto_fqn}.wire", "1"), wire_policy)
        assert len(rows) == 2
        legacy = next(row for row in rows if row.schema_version == "1.0")
        assert legacy.payload_version is None
        assert legacy.wire_policy_revision == "1"
        assert legacy.readable and legacy.writable
        assert not legacy.current and not legacy.default_write
        rows = tuple(row for row in rows if row.current)
    else:
        assert owner.accepted_wire_policies == (wire_policy,)
    assert len(rows) == 1

    row = rows[0]
    assert row.owner_ref == owner.contract_id
    assert row.dto_abi == dto_fqn
    assert row.wire_policy_ref == wire_policy[0]
    assert row.wire_policy_revision == wire_policy[1]
    assert row.schema_name == schema_name
    assert row.schema_version == schema_version
    assert row.payload_version == payload_version
    assert row.profile_ref is None
    assert row.readable and row.writable and row.current and row.default_write
    rule = get_schema_rule(registry_key, schema_version)
    assert rule is not None
    assert rule.mode is (CompatibilityMode.BACKWARD if learned_regime else CompatibilityMode.NONE)
    assert rule.notes == ()


class _StoreProbe:
    def __init__(self, store: Any) -> None:
        self.store = store
        self.put_calls = 0
        self.payload_reads = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self.store, name)

    def put_json(self, *args: Any, **kwargs: Any) -> Any:
        self.put_calls += 1
        return self.store.put_json(*args, **kwargs)

    def get_bytes(self, selector: object) -> bytes:
        self.payload_reads += 1
        return self.store.get_bytes(selector)


def _sample_frontier() -> FrontierSketch:
    return FrontierSketch(
        stage_id="test.stage",
        family="policy_design",
        sketch_type="scope_split",
        hypothesis="The diagnostic separates this extension case.",
        known_limitations=("bounded_fixture",),
        benchmark_proxy=("benchmark.member",),
        typed_integration_target="ProofBundle.dynamic_semantics",
        required_for_promotion=("independent_review",),
        canonical_contract_surface="FrontierSketch",
    )


def test_fairness_report_payload_version_is_bound_and_read_from_fresh_cas(
    tmp_path: Path,
) -> None:
    module = import_module("polisyos.ir.analytics.fairness_audit_report")
    report = module.FairnessAuditReport(
        status="PASS",
        deployable=True,
        auto_decision_allowed=True,
        audit_id="fairness.audit.version",
    )
    cas_path = tmp_path / "fairness-version"
    writer_store = ensure_ir_artifact_store(FileSystemCAS(cas_path))

    ref = module.persist_fairness_audit_report(writer_store, report)
    fresh_store = ensure_ir_artifact_store(FileSystemCAS(cas_path))
    opaque = get_json_artifact(fresh_store, ref)
    loaded = module.load_fairness_audit_report(fresh_store, ref)

    assert opaque["version"] == "1.0.0"
    assert type(loaded) is module.FairnessAuditReport
    assert loaded == report


def test_fairness_report_refuses_unregistered_payload_version_before_cas(
    tmp_path: Path,
) -> None:
    module = import_module("polisyos.ir.analytics.fairness_audit_report")
    report = module.FairnessAuditReport(
        version="9.0.0",
        status="PASS",
        deployable=True,
        auto_decision_allowed=True,
        audit_id="fairness.audit.unregistered-version",
    )
    store = _StoreProbe(ensure_ir_artifact_store(FileSystemCAS(tmp_path / "fairness-bad-version")))

    with pytest.raises(CanonViolation):
        module.persist_fairness_audit_report(store, report)

    assert store.put_calls == 0


def test_frontier_producer_persists_and_fresh_owned_reader_returns_typed_value(
    tmp_path: Path,
) -> None:
    cas_path = tmp_path / "cas"
    writer_store = ensure_ir_artifact_store(FileSystemCAS(cas_path))
    sketch = _sample_frontier()

    ref = persist_frontier_sketch(writer_store, sketch)
    fresh_store = ensure_ir_artifact_store(FileSystemCAS(cas_path))
    opaque = get_json_artifact(fresh_store, ref)
    loaded = load_frontier_sketch(fresh_store, ref)

    assert ref.manifest_profile_sha256 is not None
    assert opaque == sketch.model_dump(mode="json")
    assert type(loaded) is FrontierSketch
    assert loaded == sketch


def test_frontier_writer_refuses_unregistered_payload_version_before_cas(
    tmp_path: Path,
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    probe = _StoreProbe(store)
    malformed = _sample_frontier().model_copy(update={"schema_version": "9.0"})

    with pytest.raises(CanonViolation):
        persist_frontier_sketch(probe, malformed)

    assert probe.put_calls == 0


def test_frontier_reader_refuses_wrong_profile_before_payload_bytes(
    tmp_path: Path,
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    sketch = _sample_frontier()
    raw_ref = put_json_artifact(
        store,
        sketch.model_dump(mode="json"),
        kind="ir.frontier_sketch",
        schema_name="ir.frontier_sketch",
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=True),
    )
    probe = _StoreProbe(store)
    ref = FrontierSketchRef.model_validate(raw_ref)

    with pytest.raises(CanonViolation, match="ir_owned_artifact_profile_refused"):
        load_frontier_sketch(probe, ref)

    assert probe.payload_reads == 0


def test_frontier_reader_admits_unseen_resource_content_without_registration(
    tmp_path: Path,
) -> None:
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "unseen-resource"))
    sketch = _sample_frontier().model_copy(
        update={
            "stage_id": "extension.unseen.resource",
            "hypothesis": "A new resource follows the existing typed owner route.",
        }
    )

    ref = persist_frontier_sketch(store, sketch)
    loaded = load_frontier_sketch(store, ref)

    assert loaded.stage_id == "extension.unseen.resource"
    assert loaded == sketch


def test_registered_nondefault_representation_for_existing_owner_uses_public_route(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A runtime registry extension remains readable by the declared owner."""
    from polisyos.ir.migrations import base as migrations_base

    # Isolate the registration while preserving the real pre-existing owner rows.
    monkeypatch.setattr(
        migrations_base,
        "_SCHEMA_REGISTRY",
        {
            artifact: dict(versions)
            for artifact, versions in migrations_base._SCHEMA_REGISTRY.items()
        },
    )
    owner = import_module("polisyos.ir.analytics.frontier")._FRONTIER_SKETCH_OWNER
    wire_policy_ref, wire_policy_revision = owner.accepted_wire_policies[0]
    schema_name = "ir.frontier_sketch.registered_nondefault_test"
    registered = register_ir_representation(
        registry_key=owner.registry_key,
        owner_ref=owner.contract_id,
        dto_abi=owner.dto_fqn,
        wire_policy_ref=wire_policy_ref,
        wire_policy_revision=wire_policy_revision,
        schema_name=schema_name,
        schema_version="1.0",
        payload_version="1.0",
        profile_ref=None,
        readable=True,
        writable=True,
        current=True,
        default_write=False,
        readable_from=(),
    )
    snapshot = get_ir_owner_registry_snapshot()
    assert registered in snapshot.representations

    cas_path = tmp_path / "registered-nondefault"
    store = ensure_ir_artifact_store(FileSystemCAS(cas_path))
    sketch = _sample_frontier().model_copy(
        update={
            "stage_id": "extension.registered.nondefault",
            "hypothesis": "A registered representation uses the existing typed owner.",
        }
    )
    ref = persist_frontier_sketch(
        store,
        sketch,
        schema_name=schema_name,
        schema_version="1.0",
    )
    fresh_store = ensure_ir_artifact_store(FileSystemCAS(cas_path))
    opaque = get_json_artifact(fresh_store, ref)
    loaded = load_frontier_sketch(fresh_store, ref)

    assert store.get_manifest(ref).artifact_schema.name == schema_name
    assert opaque == sketch.model_dump(mode="json")
    assert type(loaded) is FrontierSketch
    assert loaded == sketch


_WRITER_CASES = (
    ("dp_robustness", "persist_dp_robustness_certificate", "1.0"),
    ("dynamic_causal_semantics", "persist_forecast_intervention_query", "1.0"),
    ("dynamic_causal_semantics", "persist_forecast_intervention_certificate", None),
    ("dynamic_regime", "persist_continuous_time_query", "1.0"),
    ("dynamic_regime", "persist_temporal_intervention_trajectory", "1.0"),
    ("dynamic_regime", "persist_temporal_identification_certificate", "1.0"),
    ("dynamic_regime", "persist_dynamic_treatment_regime", None),
    ("dynamic_regime", "persist_effect_trajectory_bundle", "1.0"),
    (
        "endogenous_inequality",
        "persist_endogenous_group_inequality_decomposition_result",
        "1.0",
    ),
    ("estimand", "persist_estimand_ast", "1.0"),
    ("fairness_audit_report", "persist_fairness_audit_report", "1.0.0"),
    ("forecasting_uncertainty", "persist_forecasting_uncertainty_bundle", "1.0"),
    ("frontier", "persist_frontier_sketch", "1.0"),
)


class _DumpPayload:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def model_dump(self, **_kwargs: Any) -> dict[str, Any]:
        return self.payload


@pytest.mark.parametrize(
    ("module_name", "writer_name", "payload_version"),
    _WRITER_CASES,
)
@pytest.mark.parametrize("override_field", ["schema_name", "schema_version"])
def test_every_public_writer_propagates_unregistered_schema_overrides_before_cas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    writer_name: str,
    payload_version: str | None,
    override_field: str,
) -> None:
    module = import_module(f"polisyos.ir.analytics.{module_name}")
    writer = getattr(module, writer_name)
    if writer_name == "persist_forecast_intervention_certificate":
        payload = module.ForecastInterventionCertificate(
            semantics_class="delphic",
            identified_component="expectation_only",
            announcement_node="announcement",
            intervention_time="t0",
            expectation_process_ref="expectations",
            update_operator_kind="bayes",
            admissible_intervention=True,
            graphical_oracle="delta",
            identification_method="local_independence_reweighting",
            exogeneity_checks={
                "preannouncement_orthogonalization_passed": True,
                "simultaneous_action_excluded": True,
                "anticipation_excluded": True,
            },
            support_checks={"positivity_passed": True},
        )
    else:
        version_field = "version" if module_name == "fairness_audit_report" else "schema_version"
        payload = _DumpPayload({} if payload_version is None else {version_field: payload_version})
    if module_name == "estimand":
        monkeypatch.setattr(module, "normalize_estimand_ast", lambda _value: payload)

    probe = _StoreProbe(
        ensure_ir_artifact_store(FileSystemCAS(tmp_path / f"{module_name}-{writer_name}"))
    )
    defaults = inspect.signature(writer).parameters
    kwargs = {
        "schema_name": defaults["schema_name"].default,
        "schema_version": "1.0",
    }
    if override_field == "schema_name":
        kwargs["schema_name"] = "ir.unregistered.owner-admission-test"
    else:
        kwargs["schema_version"] = "9.9"

    with pytest.raises(
        CanonViolation,
        match="ir_owned_artifact_write_override_unregistered",
    ):
        writer(probe, payload, **kwargs)

    assert probe.put_calls == 0
