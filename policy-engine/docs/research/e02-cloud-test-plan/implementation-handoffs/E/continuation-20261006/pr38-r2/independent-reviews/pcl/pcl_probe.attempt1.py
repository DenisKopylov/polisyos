"Independent PCL reviewer: actual runtime, independent arithmetic and controls."

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import shutil
import subprocess
import sys
import traceback
import types
from pathlib import Path
from unittest.mock import patch

import numpy as np
from polisyos.calibration import (
    evaluate_continuous,
    load_continuous_evaluation,
    persist_continuous_evaluation,
)
from polisyos.core.artifacts import ArtifactRef, ArtifactWriteOptions, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.foundry import (
    ExecPlan,
    LoweredIR,
    LoweredIRRef,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
)
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.api import _build_standard_derived_refs
from polisyos.foundry.methods.backends.circuit_breaker import CircuitBreakerRegistry
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.econometrics.protocols import PanelData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.calibration_diagnostics import CalibrationDiagnosticsReport
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
)


def _resolve_executable(name: str) -> str:
    "Resolve an admitted executable and refuse an unavailable program before invocation."
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


ROOT = Path("/workspace/e02-E-pr38-r2-receipts/independent-ddm-reviewer")
LEAF = Path("/workspace/e02-E-pcl-20261006")
MODE = sys.argv[1]
OUT = ROOT / MODE
OUT.mkdir(exist_ok=True)
OBSERVATIONS = []


def note(name: str, **values: object) -> None:
    record = dict(name=name, **values)
    OBSERVATIONS.append(record)
    _write_stdout(json.dumps(record, sort_keys=True), flush=True)


def put(store: object, payload: object, kind: str) -> object:
    return store.put_json(
        payload,
        ArtifactWriteOptions(
            kind=kind, media_type="application/json", schema=SchemaInfo(name=kind, version="1.0")
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def rejected(name: str, callback: object) -> None:
    try:
        callback()
    except Exception as exc:
        note(name, refused=True, exception=type(exc).__name__, message=str(exc))
    else:
        raise AssertionError(name + ": accepted")


def manual() -> None:
    store = FileSystemCAS(OUT / "analytic-cas")
    # Distinct values make the pairing-order control distinguishable. The
    # expected hit counts are stipulated by 95 centered intervals and 5 misses.
    ys = [float(3 * k) for k in range(100)]
    refs = {}
    for covered in (95, 0):
        intervals = [[value - 0.25, value + 0.25] for value in ys[:covered]] + [[-10.0, -9.0]] * (
            100 - covered
        )
        ref = persist_continuous_evaluation(
            store, evaluate_continuous(y_true=ys, intervals={0.95: intervals})
        )
        fresh = FileSystemCAS(store.root)
        reopened = load_continuous_evaluation(fresh, ref)
        counts = reopened.metadata["interval_coverage"]
        if not (
            tuple(counts[x] for x in ("requested", "eligible", "observed", "observed_pairs"))
            == (100, 100, 100, 100)
        ):
            raise AssertionError
        if not (reopened.curves["interval_coverage"][0].mean_observed == covered / 100):
            raise AssertionError
        if not (abs(reopened.metrics.ece - abs(covered / 100 - 0.95)) < 1e-14):
            raise AssertionError
        receipt = reopened.to_truthfulness_receipt()
        if not (
            receipt.runtime_truthfulness_tier
            == ("approximate_calibrated" if covered == 95 else "unverified")
        ):
            raise AssertionError
        if receipt.diagnostics["gate_eligible"] is not False:
            raise AssertionError
        note(
            f"manual_{covered}_100",
            ref=ref.model_dump(mode="json"),
            counts=counts,
            expected_hits=covered,
            measured_coverage=reopened.curves["interval_coverage"][0].mean_observed,
            tier=receipt.runtime_truthfulness_tier,
            gate_eligible=False,
        )
        refs[covered] = ref
    for name, sets, levels, denominator in [
        ("zero_pairs", [], [], (0, 0, 0)),
        (
            "missing_level_pairs",
            [[], [[v - 0.25, v + 0.25] for v in ys]],
            [0.5, 0.95],
            (200, 100, 200),
        ),
    ]:
        ref = persist_continuous_evaluation(
            store, evaluate_continuous(y_true=ys, intervals=sets, levels=levels)
        )
        reopened = load_continuous_evaluation(FileSystemCAS(store.root), ref)
        c = reopened.metadata["interval_coverage"]
        if not (tuple(c[x] for x in ("requested", "eligible", "observed")) == denominator):
            raise AssertionError
        if not (reopened.to_truthfulness_receipt().runtime_truthfulness_tier == "unverified"):
            raise AssertionError
        note(name, counts=c, expected_denominator=denominator, tier="unverified")
    payload = from_canonical_bytes(store.get_bytes(refs[95]))
    original_pairs = from_canonical_bytes(
        store.get_bytes(ArtifactRef.model_validate(payload["pairs_ref"]))
    )
    for mutation in (
        "forged_counts",
        "reordered_intervals",
        "missing_pairs",
        "missing_ref",
        "forged_receipt",
    ):
        fake = copy.deepcopy(payload)
        if mutation == "forged_counts":
            fake["report"]["metadata"]["interval_coverage"]["observed_pairs"] = 99
        elif mutation == "forged_receipt":
            fake["receipt"]["diagnostics"]["gate_eligible"] = True
        elif mutation == "missing_ref":
            fake["pairs_ref"]["artifact_id"] = "sha256:" + "f" * 64
        else:
            p = copy.deepcopy(original_pairs)
            if mutation == "reordered_intervals":
                p["intervals"][0].reverse()
            else:
                p["intervals"][0].pop()
            fake["pairs_ref"] = put(store, p, "continuous_calibration_pairs").model_dump(
                mode="json"
            )
        forged = put(store, fake, "continuous_calibration_diagnostics")
        if not (store.verify(forged).ok):
            raise AssertionError
        rejected(
            mutation,
            lambda *, forged=forged: load_continuous_evaluation(FileSystemCAS(store.root), forged),
        )
    rejected(
        "failed_intervals",
        lambda: evaluate_continuous(y_true=ys, intervals={0.95: [[1.0, 0.0]] * 100}),
    )
    naked = CalibrationDiagnosticsReport.model_validate(payload["report"])
    receipt = naked.to_truthfulness_receipt()
    if not (
        receipt.runtime_truthfulness_tier == "unverified"
        and receipt.diagnostics["gate_eligible"] is False
    ):
        raise AssertionError
    if "interval_pairs_not_reconciled" not in receipt.degradation_reasons:
        raise AssertionError
    note(
        "report_ref_never_seen",
        tier=receipt.runtime_truthfulness_tier,
        gate_eligible=False,
        degradation_reasons=receipt.degradation_reasons,
    )
    from polisyos.calibration import CalibrationPoint, CalibrationResult, compute_calibration_curve
    from polisyos.scientist.methods.backtesting.calibration_curve import (
        CalibrationPoint as LegacyCalibrationPoint,
    )
    from polisyos.scientist.methods.backtesting.calibration_curve import (
        CalibrationResult as LegacyCalibrationResult,
    )
    from polisyos.scientist.methods.backtesting.calibration_curve import (
        compute_calibration_curve as compute,
    )

    if not (
        CalibrationPoint is LegacyCalibrationPoint
        and CalibrationResult is LegacyCalibrationResult
        and compute_calibration_curve is compute
    ):
        raise AssertionError
    note(
        "compatibility_alias",
        identical_objects=3,
        lifecycle_window="calibration + Scientist owners; not retired",
    )


def blob_module(module_name: str, source: object) -> object:
    old = importlib.import_module(module_name)
    new = types.ModuleType(module_name)
    new.__file__ = old.__file__
    new.__package__ = old.__package__
    sys.modules[module_name] = new
    exec(compile(source, new.__file__, "exec"), new.__dict__)  # noqa: S102 - isolated removal control executes exact Git/AST fixture, never external input
    return new


def native() -> None:
    advanced = importlib.import_module("polisyos.foundry.methods.catalog.econometrics.advanced")
    numpy_runner = importlib.import_module("polisyos.foundry.methods.backends.numpy_runner")
    graph = importlib.import_module("polisyos.foundry.execute._internal.graph")
    if MODE == "old_base":
        # Exact 229988 graph+runner+Advanced blobs, kept in separate namespaces.
        for module in (advanced, numpy_runner, graph):
            relative = Path(module.__file__).relative_to(LEAF)
            source = subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
                [
                    _resolve_executable("git"),
                    "show",
                    "22998874b5f32434c462065baaca44a78e967f91:" + str(relative),
                ],
                cwd=LEAF,
            ).decode()
            note(
                "exact_base_blob",
                module=module.__name__,
                sha256=hashlib.sha256(source.encode()).hexdigest(),
            )
            new = blob_module(module.__name__, source)
            if module is advanced:
                advanced = new
            elif module is numpy_runner:
                numpy_runner = new
            else:
                graph = new
    elif MODE == "remove_graph_store":
        source = Path(graph.__file__).read_text()
        removed = source.replace(
            'method_params["artifact_store"] = store', 'method_params["artifact_store"] = None'
        )
        if not (removed != source):
            raise AssertionError
        graph = blob_module(graph.__name__, removed)
        note(
            "present_but_fake_removal",
            field="artifact_store",
            fields_preserved=True,
            behavior="configured store suppressed",
        )
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    CircuitBreakerRegistry.reset_instance()
    cls = advanced.NonstationaryGARCHEstimator
    signature_before = cls.signature.stable_digest()
    if not ("artifact_store" not in {p.name for p in cls.signature.parameters}):
        raise AssertionError
    MethodRegistry.get_instance().register(cls)
    store = FileSystemCAS(OUT / "native-cas")
    ir = ArtifactRef(
        artifact_id="sha256:" + "b" * 64, kind="ir.trinity_bundle", media_type="application/json"
    )
    lowered = store.put_json(
        LoweredIR(ir_ref=ir, mechanisms=[], constraints=[]),
        ArtifactWriteOptions(kind="foundry.lowered_ir", media_type="application/json"),
    )
    params = {
        "max_breaks": 0,
        "break_detection_method": "none",
        "min_segment_length": 12,
        "holdout_periods": 50,
        "nominal_coverage": 0.95,
        "diagnostic_levels": (0.95,),
        "variance_feature_names": (),
        "run_policy_benchmark": True,
        "artifact_store": "client-untrusted-service",
    }
    node = ProgramNode(
        node_id="independent-pcl",
        node_kind="method",
        method_fqn=cls.signature.fqn,
        method_params=params,
    )
    pg = ProgramGraph(
        ir_ref=ir,
        lowered_ir_ref=LoweredIRRef(artifact_id=lowered.artifact_id),
        nodes=[node],
        entrypoints=[node.node_id],
    )
    pgref = store.put_json(
        pg,
        ArtifactWriteOptions(kind="foundry.program_graph", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    plan = ExecPlan(
        program_ref=ProgramGraphRef(artifact_id=pgref.artifact_id), order=[node.node_id]
    )
    planref = store.put_json(
        plan, ArtifactWriteOptions(kind="foundry.exec_plan", media_type="application/json")
    )
    r = np.random.default_rng(840912)
    pd = PanelData(
        dependent=r.normal(scale=0.2, size=160),
        exog=np.zeros((160, 1)),
        entity_ids=np.repeat([7, 12], 80),
        time_ids=np.tile(np.arange(80), 2),
        feature_names=["constant"],
        metadata={
            "target_id": "reviewer-synthetic-returns",
            "unit": "dimensionless-return",
            "group_labels": ["review", "review"],
        },
    )

    class State(dict):
        def __init__(self) -> None:
            super().__init__(pd.model_dump(mode="python"))
            empty = GlobalState.empty(n_agents=1, n_firms=1)
            self.agents, self.firms = empty.agents, empty.firms

    state = State()
    before = copy.deepcopy(dict(state))
    trace = []
    original_summary = advanced._summarize_interval_diagnostics

    def transparent_summary(**kwargs: object) -> object:
        value = original_summary(**kwargs)
        trace.append(
            {
                "caller": traceback.extract_stack(limit=3)[-2].name,
                "store_is_configured": kwargs.get("calibration_store") is store,
                "ref": None
                if value["calibration_ref"] is None
                else str(value["calibration_ref"].artifact_id),
                "rows": len(kwargs["y_values"]),
            }
        )
        return value

    with patch.object(advanced, "_summarize_interval_diagnostics", transparent_summary):
        artifacts = graph.execute_program_graph(
            store,
            program_ref=pgref,
            exec_plan_ref=planref,
            base_state=state,
            mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            seed=5907,
        )
    refs = artifacts.derived_artifacts
    note(
        "actual_graph",
        degraded=artifacts.is_degraded,
        derived_roles=[role for role, _ in refs],
        summary_calls=trace,
    )
    if MODE in ("old_base", "remove_graph_store"):
        if not (refs == () and all(x["ref"] is None for x in trace)):
            raise AssertionError
        note(
            "old_proxy_divergence",
            native_execution_completed=True,
            persisted_pair_refs=0,
            configured_property_absent=True,
        )
        return
    if not (not artifacts.is_degraded and len(refs) == 5):
        raise AssertionError
    if not (len(trace) == 5 and all(item["store_is_configured"] and item["ref"] for item in trace)):
        raise AssertionError
    if not (
        sorted({x["caller"] for x in trace})
        == [
            "_evaluate_panel_volatility_scenario",
            "pure_step",
        ]
    ):
        raise AssertionError
    fresh = FileSystemCAS(store.root)
    for role, ref in refs:
        a = from_canonical_bytes(fresh.get_bytes(ref))
        p = from_canonical_bytes(fresh.get_bytes(ArtifactRef.model_validate(a["pairs_ref"])))
        binding = a["source_binding"]
        s = from_canonical_bytes(
            fresh.get_bytes(ArtifactRef.model_validate(binding["source_data_ref"]))
        )
        rows = binding["evaluated_rows"]
        if not (len(rows) == len(p["y_true"]) == 100):
            raise AssertionError
        keys = [(x["entity_id"], x["observation_time_id"]) for x in rows]
        if not (len(set(keys)) == 100):
            raise AssertionError
        expected_keys = {(entity, t) for entity in (7, 12) for t in range(30, 80)}
        if not (set(keys) == expected_keys):
            raise AssertionError
        if not (
            all(
                x["training_start_time_id"] == 0
                and x["training_end_time_id"] == 29
                and x["evaluation_mode"] == "blocked_holdout"
                and x["forecast_horizon"] == x["observation_time_id"] - 29
                for x in rows
            )
        ):
            raise AssertionError
        source_ys = [s["dependent"][x["source_row_index"]] for x in rows]
        if not (source_ys == p["y_true"]):
            raise AssertionError
        if not (
            all(
                s["entity_ids"][x["source_row_index"]] == x["entity_id"]
                and s["time_ids"][x["source_row_index"]] == x["observation_time_id"]
                for x in rows
            )
        ):
            raise AssertionError
        # Fresh source bytes and stored interval endpoints define numerator;
        # report counts and producer covered arrays are not the oracle.
        hits = sum(
            lower <= outcome <= upper
            for outcome, (lower, upper) in zip(source_ys, p["intervals"][0], strict=True)
        )
        report = load_continuous_evaluation(fresh, ref)
        counts = report.metadata["interval_coverage"]
        if not (tuple(counts[k] for k in ("requested", "eligible", "observed")) == (100, 100, 100)):
            raise AssertionError
        if not (report.curves["interval_coverage"][0].mean_observed == hits / 100):
            raise AssertionError
        if not (abs(report.metrics.ece - abs(hits / 100 - 0.95)) < 1e-14):
            raise AssertionError
        if not (
            a["gate_eligible"] is False
            and report.to_truthfulness_receipt().diagnostics["gate_eligible"] is False
        ):
            raise AssertionError
        if not (binding["source_authority_basis"] == "not_established"):
            raise AssertionError
        note(
            "fresh_native_read",
            role=role,
            ref=str(ref.artifact_id),
            pairs_ref=p["protocol"] + ":" + str(a["pairs_ref"]["artifact_id"]),
            source_ref=str(binding["source_data_ref"]["artifact_id"]),
            rows=100,
            unique_keys=100,
            independent_hits=hits,
            requested=100,
            eligible=100,
            observed=100,
            authority="not_established",
            gate_eligible=False,
        )
    public = _build_standard_derived_refs(artifacts)
    if not (
        {(i.role, str(i.ref.artifact_id)) for i in public if ":calibration." in i.role}
        == {(role, str(ref.artifact_id)) for role, ref in refs}
    ):
        raise AssertionError
    storedgraph = from_canonical_bytes(store.get_bytes(pgref))
    if not (
        storedgraph["nodes"][0]["method_params"]["artifact_store"] == "client-untrusted-service"
    ):
        raise AssertionError
    for name in ("dependent", "exog", "entity_ids", "time_ids"):
        np.testing.assert_array_equal(state[name], before[name])
    if not ("artifact_store" not in state):
        raise AssertionError
    if not (from_canonical_bytes(store.get_bytes(artifacts.state_delta_ref))["ops"] == []):
        raise AssertionError
    if not (cls.signature.stable_digest() == signature_before):
        raise AssertionError
    note(
        "service_isolation",
        signature_stable_digest=signature_before,
        state_delta_ops=0,
        source_state_unchanged=True,
        client_metadata_unchanged=True,
        graph_service_overridden=True,
        public_refs=5,
        numpy_compile_cache="not used; supports_jit=false",
    )


try:
    if MODE == "manual":
        manual()
    else:
        native()
except Exception:
    traceback.print_exc()
    raise
finally:
    (OUT / "observations.json").write_text(
        json.dumps(OBSERVATIONS, indent=2, sort_keys=True) + "\n"
    )
