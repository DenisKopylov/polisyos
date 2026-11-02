from decimal import Decimal

import jax.numpy as jnp
import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import (
    ExecPlan,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
)
from polisyos.foundry.calibration.calibrator import Calibrator, CalibratorInputs
from polisyos.foundry.contracts.state import GlobalState
from polisyos.ir.analytics.calibration import (
    CalibrationConfig,
    CalibrationTarget,
    TrainableParamRef,
)
from polisyos.ir.kernel.constraints import DEFAULT_CONSTRAINT_REGISTRY
from polisyos.ir.kernel.mechanisms import (
    DEFAULT_MECHANISM_REGISTRY,
    MechanismTypeRegistry,
    MechanismTypeSpec,
    ParamSpec,
    ParamType,
)
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY


def _dummy_artifact() -> ArtifactID:
    return ArtifactID.from_sha256_hex("0" * 64)


def _build_graph(nodes: list[ProgramNode]) -> tuple[ProgramGraph, ExecPlan]:
    dummy_id = _dummy_artifact()
    policy_ref = ArtifactRef(
        artifact_id=dummy_id,
        kind="ir.trinity_bundle",
        media_type="application/json",
    )
    program_ref = ProgramGraphRef(artifact_id=dummy_id)
    program_graph = ProgramGraph(ir_ref=policy_ref, nodes=nodes, edges=[], entrypoints=[])
    exec_plan = ExecPlan(program_ref=program_ref, order=[node.node_id for node in nodes])
    return program_graph, exec_plan


def _base_state(n_agents: int = 5) -> GlobalState:
    base_state = GlobalState.empty(n_agents=n_agents, n_firms=1)
    return base_state.replace(
        agents=base_state.agents.replace(
            income=jnp.ones(n_agents) * 100.0,
            reported_income=jnp.ones(n_agents) * 100.0,
        ),
        government_balance=jnp.array(0.0),
    )


@pytest.mark.parametrize("source_mode", ["measurement", "fetcher"])
def test_selected_observation_targets_reach_real_optimizer_and_fresh_report(
    tmp_path, record_property, monkeypatch, source_mode
):
    """A synthetic selected source keeps its axis/unit/support through native fitting.

    Model ticks are explicitly positional; the source's calendar dates are
    report metadata, not a claim of monthly dynamics or empirical adequacy.
    """
    from datetime import date

    import numpy as np
    import pandas as pd

    from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
    from polisyos.core.artifacts import load_core_json_artifact as read_json
    from polisyos.core.canon import CanonSpec
    from polisyos.foundry.calibration.execution_basis import (
        canonical_input_sha256,
        load_calibration_execution_input_basis,
        read_calibration_report_source,
    )
    from polisyos.foundry.calibration.measurement import CalibrationTargetBundleCompiler
    from polisyos.ir.analytics.calibration import TargetAlignConfig, TargetLossConfig
    from polisyos.ir.analytics.data_views import AccessTier, DataViewRequest, DataViewType
    from polisyos.ir.model_layer.types import TimeFrequency
    from polisyos.ir.observation.compiler import (
        CalibrationSplitLabel,
        CalibrationSplitPlan,
        CalibrationSplitter,
        CalibrationSplitWindow,
    )
    from polisyos.ir.observation.contracts import (
        EntityScope,
        IdentificationMode,
        ObservationFamily,
        ObservationPanel,
        ObservationRecord,
        SourceConfidenceTier,
    )

    records = [
        ObservationRecord(
            observation_id=f"native_tax_{month}",
            family=ObservationFamily.BUDGET_FLOWS,
            time_grain=TimeFrequency.MONTH,
            period_start=date(2024, month, 1),
            period_end=date(2024, month, 1),
            entity_scope=EntityScope.GLOBAL,
            metric_id="government_balance",
            observed_value=value,
            unit="currency",
            coverage_estimate=1.0,
            trust_weight=1.0,
            source_id="controlled_tax_observations",
            source_version="fixture.v1",
            regime_id="fixture",
            schema_regime_id="fixture.v1",
            identification_mode=IdentificationMode.POINT_IDENTIFIED,
            source_confidence_tier=SourceConfidenceTier.CORE,
            notes_json={"fixture_tick": tick, "authority": "synthetic_candidate"},
        )
        for month, value, tick in [(2, 100.0, 1), (1, 50.0, 0)]
    ]
    panel = ObservationPanel(
        panel_id="native_selected_tax_panel",
        family=ObservationFamily.BUDGET_FLOWS,
        time_grain=TimeFrequency.MONTH,
        records=records,
    )
    root = tmp_path / "native_calibration"
    store = FileSystemCAS(root)
    selected_panel = store.put_json(
        panel,
        PutOptions(
            kind="ir.observation_panel",
            media_type="application/json",
            schema=SchemaInfo(name="fixture.ObservationPanel", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    source_bytes = FileSystemCAS(root).get_bytes(selected_panel)
    captured = ObservationPanel.model_validate(read_json(FileSystemCAS(root), selected_panel))
    compiler = CalibrationTargetBundleCompiler(
        splitter=CalibrationSplitter(
            split_plan=CalibrationSplitPlan(
                windows=[CalibrationSplitWindow(label=CalibrationSplitLabel.TRAIN)]
            )
        )
    )
    measured = compiler.compile(captured)
    target_id = measured.targets[0].target_id
    assert measured.time_axis[target_id] == ("2024-01-01", "2024-02-01")
    assert measured.observation_id[target_id] == ("native_tax_1", "native_tax_2")
    assert measured.targets[0].unit == "currency"
    np.testing.assert_array_equal(measured.observed_value[target_id], [50.0, 100.0])
    assert measured.split_label[target_id] == ("train", "train")

    request = DataViewRequest(
        request_id="controlled_tax_request",
        run_id="native_cal01",
        view_type=DataViewType.PANEL,
        metrics=["government_balance"],
        access_tier=AccessTier.PUBLIC,
    )
    target = CalibrationTarget(
        target_id=target_id,
        model_metric_path="government_balance",
        fabric_metric="government_balance",
        fabric_query=request.model_dump(mode="json") if source_mode == "fetcher" else None,
        align=TargetAlignConfig(time_column="fixture_tick"),
        loss=TargetLossConfig(relative=False),
    )
    config = CalibrationConfig(
        targets=[target], steps=2, max_steps=60, learning_rate=0.1, hessian={"enabled": False}
    )
    graph, plan = _build_graph(
        [
            ProgramNode(
                node_id="tax",
                node_kind="mechanism",
                mechanism_type="income_tax",
                outputs=["agents.income", "government.balance"],
            )
        ]
    )

    def fetch_actual_selected_source(_target, _request):
        fresh_panel = ObservationPanel.model_validate(
            read_json(FileSystemCAS(root), selected_panel)
        )
        return pd.DataFrame(
            {
                "government_balance": [row.observed_value for row in fresh_panel.records],
                "fixture_tick": [row.notes_json["fixture_tick"] for row in fresh_panel.records],
            }
        )

    def inputs(bundle=measured):
        return CalibratorInputs(
            config=config,
            program_graph=graph,
            exec_plan=plan,
            base_state=_base_state(5),
            mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            selector_field_registry=None,
            parameter_loader=lambda _: {
                "params": {"rate": 0.3},
                "schedule": {"start_step": 0, "end_step": 100},
            },
            measurement_bundle=bundle if source_mode == "measurement" else None,
            target_fetcher=fetch_actual_selected_source if source_mode == "fetcher" else None,
            controls_seq=jnp.arange(2),
        )

    if source_mode == "measurement":
        from dataclasses import replace

        for invalid_axis in ([float("nan"), 1.0], [0.0, 1.0]):
            invalid_config = config.model_copy(update={"time_axis": invalid_axis})
            with pytest.raises(ValueError, match="[Tt]ime|axis"):
                Calibrator(replace(inputs(), config=invalid_config)).run()
        with pytest.raises(ValueError, match="steps"):
            Calibrator(replace(inputs(), config=config.model_copy(update={"steps": 3}))).run()
        for invalid_source in (("not_a_date", "2024-02-01"), (0.0, float("inf")), (1.0, 1.0)):
            invalid_bundle = replace(measured, time_axis={target_id: invalid_source})
            with pytest.raises(ValueError, match="[Tt]ime|axis"):
                Calibrator(inputs(invalid_bundle)).run()
        # Exact calendar labels may be declared; they do not assert physical
        # calendar dynamics for this positional synthetic model.
        config = config.model_copy(
            update={"time_axis": [float(date(2024, month, 1).toordinal()) for month in (1, 2)]}
        )

    report, selected_report = Calibrator(inputs()).run_and_persist(store)
    fresh = FileSystemCAS(root)
    restored = read_calibration_report_source(fresh, ref=selected_report).require_value()
    assert restored.model_dump(mode="json") == report.model_dump(mode="json")
    assert restored.calibrated_params["tax.rate"] == pytest.approx(0.1, rel=0.2)
    assert restored.total_loss < 1.0
    assert restored.grad_norm_history and np.all(np.isfinite(restored.grad_norm_history))
    assert restored.loss_history and np.all(np.isfinite(restored.loss_history))
    np.testing.assert_allclose(restored.series_comparison[target_id].real, [50.0, 100.0])
    manifest = fresh.get_manifest(selected_report)
    basis_edge = next(
        edge for edge in manifest.inputs if edge.role == "calibration_execution_input_basis"
    )
    basis_ref = ArtifactRef(
        artifact_id=basis_edge.artifact_id,
        kind="foundry.calibration_execution_input_basis",
        media_type="application/json",
        manifest_profile_sha256=basis_edge.manifest_profile_sha256,
    )
    basis = load_calibration_execution_input_basis(fresh, basis_ref)
    identity = next(item for item in basis.target_inputs if item.target_id == target_id)
    assert identity.unit_status == "not_established"
    assert identity.physical_time_status == "not_established"
    if source_mode == "measurement":
        declaration = restored.execution_context["measurement_target_semantics"][target_id]
        assert declaration == {
            "declared_unit": "currency",
            "interval_semantics": "point",
            "period_end": ["2024-01-01", "2024-02-01"],
            "unit_authority": "not_established",
        }
        assert identity.observation_ids == ("native_tax_1", "native_tax_2")
        assert identity.split_labels == ("train", "train")
        metadata = {
            name: getattr(measured, name).get(target_id)
            for name in (
                "trust_weight",
                "coverage_estimate",
                "censoring_mask",
                "lag_days_estimate",
                "shock_mask",
                "schema_regime_id",
                "observation_id",
                "time_axis",
                "split_label",
                "identification_mode",
                "time_grain",
                "period_end",
            )
        }
        metadata["target_spec"] = measured.targets[0].model_dump(mode="python")
        assert identity.measurement_metadata_sha256 == canonical_input_sha256(metadata)
        assert restored.series_comparison[target_id].time == [
            float(date(2024, month, 1).toordinal()) for month in (1, 2)
        ]
        unsupported = compiler.compile(
            captured.model_copy(
                update={
                    "records": [
                        row.model_copy(update={"coverage_estimate": 0.0})
                        for row in captured.records
                    ]
                }
            )
        )
        with pytest.raises(ValueError, match="no_effective_support"):
            Calibrator(inputs(unsupported)).run()
    else:
        assert restored.series_comparison[target_id].time == [0.0, 1.0]
        from polisyos.foundry.calibration import preflight as preflight_owner

        # Delete only paired admission while keeping the same actual source,
        # optimizer, configuration, expected observations and report producer.
        # The old equal-length shortcut then fits [100,50] against a growing
        # balance, whose independent least-squares optimum is rate .08 rather
        # than .1, with MSE2250 rather than a good fit.
        with monkeypatch.context() as removed:
            removed.setattr(
                preflight_owner, "_admit_source_axis", lambda values, time: (values, time)
            )
            counterfactual = Calibrator(inputs()).run()
        assert counterfactual.calibrated_params["tax.rate"] == pytest.approx(0.08, rel=0.2)
        assert counterfactual.total_loss > 2000.0
        assert counterfactual.series_comparison[target_id].real == [100.0, 50.0]
    assert fresh.get_bytes(selected_panel) == source_bytes
    record_property("selected_source_ref", selected_panel.model_dump_json())
    record_property("selected_report_ref", selected_report.model_dump_json())


def test_calibrator_recovers_income_tax_rate():
    n_agents = 5
    base_state = _base_state(n_agents=n_agents)

    # Один шаг: ожидаем баланс ~ 50.0 при истинном rate=0.1
    target_series = jnp.array([50.0], dtype=jnp.float32)
    config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="gov_balance",
                model_metric_path="government_balance",
                fabric_query=None,
            )
        ],
        max_steps=60,
        learning_rate=0.1,
        seed=0,
        hessian={"enabled": False},
    )

    node = ProgramNode(
        node_id="tax",
        node_kind="mechanism",
        mechanism_type="income_tax",
        params_ref=None,
        outputs=["agents.income", "government.balance"],
    )
    program_graph, exec_plan = _build_graph([node])

    def loader(_):
        # Стартовое значение ближе к 0.3, чтобы калибровка сходилась к 0.1
        return {"params": {"rate": 0.3}, "schedule": {"start_step": 0, "end_step": 100}}

    inputs = CalibratorInputs(
        config=config,
        program_graph=program_graph,
        exec_plan=exec_plan,
        base_state=base_state,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=None,
        parameter_loader=loader,
        raw_targets={"gov_balance": target_series},
        controls_seq=jnp.arange(target_series.shape[0]),
    )

    calibrator = Calibrator(inputs)
    report = calibrator.run()

    calibrated_rate = report.calibrated_params.get("tax.rate")
    assert calibrated_rate is not None
    # Ожидаем, что калибратор приблизится к истинному 0.1 (допускаем 20% погрешность)
    assert pytest.approx(0.1, rel=0.2) == calibrated_rate
    assert report.total_loss < 1.0
    assert report.fit_quality is not None


def test_calibrator_resolves_slot_id_metric():
    n_agents = 3
    base_state = _base_state(n_agents=n_agents)
    target_series = jnp.array([30.0], dtype=jnp.float32)
    config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="gov_balance",
                model_metric_path="government.balance",
                fabric_query=None,
            )
        ],
        max_steps=40,
        learning_rate=0.1,
        seed=0,
        hessian={"enabled": False},
    )

    node = ProgramNode(
        node_id="tax",
        node_kind="mechanism",
        mechanism_type="income_tax",
        params_ref=None,
        outputs=["agents.income", "government.balance"],
    )
    program_graph, exec_plan = _build_graph([node])

    def loader(_):
        return {"params": {"rate": 0.3}, "schedule": {"start_step": 0, "end_step": 10}}

    inputs = CalibratorInputs(
        config=config,
        program_graph=program_graph,
        exec_plan=exec_plan,
        base_state=base_state,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=None,
        parameter_loader=loader,
        raw_targets={"gov_balance": target_series},
        controls_seq=jnp.arange(target_series.shape[0]),
    )

    report = Calibrator(inputs).run()
    calibrated_rate = report.calibrated_params.get("tax.rate")
    assert calibrated_rate is not None
    assert pytest.approx(0.1, rel=0.2) == calibrated_rate


def test_calibrator_trainable_filtering():
    base_state = _base_state(n_agents=1)
    target_series = jnp.array([20.0], dtype=jnp.float32)
    config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="gov_balance",
                model_metric_path="government_balance",
                fabric_query=None,
            )
        ],
        trainables=[TrainableParamRef(param_id="rate", node_id="tax")],
        max_steps=40,
        learning_rate=0.1,
        seed=0,
        hessian={"enabled": False},
    )

    nodes = [
        ProgramNode(
            node_id="tax",
            node_kind="mechanism",
            mechanism_type="income_tax",
            params_ref=None,
            outputs=["agents.income", "government.balance"],
        ),
        ProgramNode(
            node_id="subsidy",
            node_kind="mechanism",
            mechanism_type="tax_subsidy",
            params_ref=None,
            outputs=["agents.income", "government.balance"],
        ),
    ]
    program_graph, exec_plan = _build_graph(nodes)

    def loader(node):
        node_id = getattr(node, "node_id", "")
        rate = 0.2 if node_id == "tax" else 0.3
        return {"params": {"rate": rate}, "schedule": {"start_step": 0, "end_step": 10}}

    inputs = CalibratorInputs(
        config=config,
        program_graph=program_graph,
        exec_plan=exec_plan,
        base_state=base_state,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=None,
        parameter_loader=loader,
        raw_targets={"gov_balance": target_series},
        controls_seq=jnp.arange(target_series.shape[0]),
    )

    report = Calibrator(inputs).run()
    assert pytest.approx(0.3, rel=1e-6) == report.calibrated_params["subsidy.rate"]


def test_calibrator_constraint_penalty():
    base_state = _base_state(n_agents=1)
    target_series = jnp.array([0.0], dtype=jnp.float32)
    config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="gov_balance",
                model_metric_path="government_balance",
                fabric_query=None,
                loss={"weight": 0.0},
            )
        ],
        max_steps=10,
        learning_rate=0.05,
        seed=0,
        constraint_loss={"enabled": True, "weight": 1.0},
        constraint_values={"min_balance": 1000.0},
        hessian={"enabled": False},
    )

    node = ProgramNode(
        node_id="tax",
        node_kind="mechanism",
        mechanism_type="income_tax",
        params_ref=None,
        outputs=["agents.income", "government.balance"],
    )
    program_graph, exec_plan = _build_graph([node])

    def loader(_):
        return {"params": {"rate": 0.1}, "schedule": {"start_step": 0, "end_step": 10}}

    inputs = CalibratorInputs(
        config=config,
        program_graph=program_graph,
        exec_plan=exec_plan,
        base_state=base_state,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=None,
        constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
        parameter_loader=loader,
        raw_targets={"gov_balance": target_series},
        controls_seq=jnp.arange(target_series.shape[0]),
    )

    report = Calibrator(inputs).run()
    assert report.total_loss > sum(report.per_target_loss.values())


def test_calibrator_prior_penalty():
    base_state = _base_state(n_agents=1)
    target_series = jnp.array([0.0], dtype=jnp.float32)
    mechanism_registry = MechanismTypeRegistry(
        mechanisms={
            "income_tax": MechanismTypeSpec(
                mechanism_id="income_tax",
                params={
                    "rate": ParamSpec(
                        param_id="rate",
                        required=True,
                        value_type=ParamType.RATE,
                        min_value=Decimal("0"),
                        max_value=Decimal("1"),
                        trainable=True,
                        prior_mean=Decimal("0.5"),
                        prior_std=Decimal("0.1"),
                        unit_id="ratio",
                    )
                },
                reads_slots=["agents.reported_income"],
                writes_slots=["agents.income", "government.balance"],
                default_merge={"agents.income": "sum", "government.balance": "sum"},
            )
        }
    )
    config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="gov_balance",
                model_metric_path="government_balance",
                fabric_query=None,
                loss={"weight": 0.0},
            )
        ],
        max_steps=1,
        learning_rate=1e-6,
        seed=0,
        prior_loss={"enabled": True, "weight": 1.0},
        hessian={"enabled": False},
    )

    node = ProgramNode(
        node_id="tax",
        node_kind="mechanism",
        mechanism_type="income_tax",
        params_ref=None,
        outputs=["agents.income", "government.balance"],
    )
    program_graph, exec_plan = _build_graph([node])

    def loader(_):
        return {"params": {"rate": 0.1}, "schedule": {"start_step": 0, "end_step": 10}}

    inputs = CalibratorInputs(
        config=config,
        program_graph=program_graph,
        exec_plan=exec_plan,
        base_state=base_state,
        mechanism_registry=mechanism_registry,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=None,
        parameter_loader=loader,
        raw_targets={"gov_balance": target_series},
        controls_seq=jnp.arange(target_series.shape[0]),
    )

    report = Calibrator(inputs).run()
    calibrated_rate = report.calibrated_params["tax.rate"]
    expected = ((calibrated_rate - 0.5) / (0.1 + config.prior_loss.epsilon)) ** 2
    assert pytest.approx(expected, rel=1e-3) == report.total_loss


def test_calibrator_gradnorm_updates_weights():
    base_state = _base_state(n_agents=1)
    targets = {
        "gov_balance": jnp.array([1000.0], dtype=jnp.float32),
        "avg_income": jnp.array([10.0], dtype=jnp.float32),
    }
    config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="gov_balance",
                model_metric_path="government_balance",
                fabric_query=None,
                loss={"relative": False, "weight": 1.0},
            ),
            CalibrationTarget(
                target_id="avg_income",
                model_metric_path="agents.income",
                fabric_query=None,
                aggregation="mean",
            ),
        ],
        max_steps=5,
        learning_rate=0.1,
        seed=0,
        grad_norm={"enabled": True, "update_every": 1, "lr": 0.5},
        hessian={"enabled": False},
    )

    node = ProgramNode(
        node_id="tax",
        node_kind="mechanism",
        mechanism_type="income_tax",
        params_ref=None,
        outputs=["agents.income", "government.balance"],
    )
    program_graph, exec_plan = _build_graph([node])

    def loader(_):
        return {"params": {"rate": 0.2}, "schedule": {"start_step": 0, "end_step": 10}}

    inputs = CalibratorInputs(
        config=config,
        program_graph=program_graph,
        exec_plan=exec_plan,
        base_state=base_state,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=None,
        parameter_loader=loader,
        raw_targets=targets,
        controls_seq=jnp.arange(1),
    )

    report = Calibrator(inputs).run()
    weights = report.target_weights
    assert abs(weights["gov_balance"] - weights["avg_income"]) > 1e-3


def test_calibrator_hessian_uncertainty():
    base_state = _base_state(n_agents=1)
    target_series = jnp.array([10.0], dtype=jnp.float32)
    config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="gov_balance",
                model_metric_path="government_balance",
                fabric_query=None,
            )
        ],
        max_steps=20,
        learning_rate=0.1,
        seed=0,
        hessian={"enabled": True, "damping": 1e-6},
    )

    node = ProgramNode(
        node_id="tax",
        node_kind="mechanism",
        mechanism_type="income_tax",
        params_ref=None,
        outputs=["agents.income", "government.balance"],
    )
    program_graph, exec_plan = _build_graph([node])

    def loader(_):
        return {"params": {"rate": 0.2}, "schedule": {"start_step": 0, "end_step": 10}}

    inputs = CalibratorInputs(
        config=config,
        program_graph=program_graph,
        exec_plan=exec_plan,
        base_state=base_state,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=None,
        parameter_loader=loader,
        raw_targets={"gov_balance": target_series},
        controls_seq=jnp.arange(target_series.shape[0]),
    )

    report = Calibrator(inputs).run()
    uncertainties = report.uncertainties
    assert uncertainties is not None
    assert len(uncertainties.params) == 1
    assert len(uncertainties.std) == 1
    assert len(uncertainties.correlation) == 1
    assert pytest.approx(1.0, rel=1e-6) == uncertainties.correlation[0][0]
