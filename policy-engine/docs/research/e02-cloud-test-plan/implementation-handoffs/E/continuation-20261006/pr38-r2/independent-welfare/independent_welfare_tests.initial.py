"""Independent native GE mathematical law, support and CAS controls."""

import copy
import hashlib
import json
import logging
import os
import platform
import sys
from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts import ExecPlanRef, Metrics, MetricsRef, SimulationResult
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    NumericPolicySpec,
    NumericToleranceMode,
    ParametricFitCarrier,
    PosteriorSamplesCarrier,
    QuantileSummaryCarrier,
    UncertaintyEnvelope,
    UncertaintySource,
    persist_uncertainty_envelope,
)
from polisyos.ir.analytics.welfare import load_welfare_bundle
from polisyos.scientist.nodes.builtins.simulate import propagate_welfare as node
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_WELFARE_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

RESULTS = []


def envelope(atoms: object = (0.0, 1.0), weights: object = (3.0, 1.0)) -> object:
    return UncertaintyEnvelope(
        numeric_policy=NumericPolicySpec(mode=NumericToleranceMode.DECIMAL_EXACT),
        point_estimate=0.25,
        confidence_interval=(0.0, 1.0),
        confidence_level=None,
        distribution_family=DistributionFamily.BOOTSTRAP,
        source=UncertaintySource.ENSEMBLE,
        interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
        is_heuristic_ci=True,
        gate_eligible=False,
        distribution_payload=PosteriorSamplesCarrier(
            samples=atoms, weights=weights, sample_axis="independent_row"
        ),
    )


def fixture(root: object, env: object = None) -> tuple[object, ...]:
    root = Path(root)
    store = FileSystemCAS(root)
    registry = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry, run_id="independent-welfare-ge")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("independent-welfare-ge"))
    plan = store.put_json(
        {
            "program_ref": {
                "artifact_id": "sha256:" + "0" * 64,
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics = store.put_json(
        Metrics(values={"response": 2.0}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    sim = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=plan.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    ref = persist_uncertainty_envelope(store, envelope() if env is None else env)
    state = ExperimentState(
        run_id="independent-welfare-ge",
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: sim},
        params={
            "welfare_config": {
                "metric_order": ["response"],
                "pe_response": [2.0],
                "weights": [1.0],
                "ge_technical_coefficients": [[0.25]],
                "ge_entry_map": {"A": [0, 0]},
                "input_envelopes": {"A": ref.model_dump(mode="json")},
                "credible_method": "monte_carlo",
            },
            "propagation_config": {
                "mc_n_samples": 128,
                "mc_min_valid_samples": 10,
                "mc_seed": 31415,
            },
        },
    )
    return ctx, state, ref


def run(root: object, env: object = None) -> tuple[object, ...]:
    ctx, state, ref = fixture(root, env)
    outcome = node.PropagateWelfareNode().execute(ctx, state)
    if not (outcome.status == "ok"):
        raise AssertionError(outcome.error)
    fresh = FileSystemCAS(root)
    bundle_ref = outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]
    bundle = load_welfare_bundle(fresh, bundle_ref)
    receipt_ref = node.ArtifactRef.model_validate(bundle.diagnostics["draw_outcomes_ref"])
    receipt = node._load_welfare_draw_outcomes(fresh, receipt_ref)
    samples = node._load_verified_welfare_samples(FileSystemCAS(root), bundle.sample_bundle_ref)
    report = from_canonical_bytes(fresh.get_bytes(bundle.diagnostics["propagation_report_ref"]))
    RESULTS.append(
        {
            "cas": str(root),
            "source_ref": ref.model_dump(mode="json"),
            "bundle_ref": bundle_ref.model_dump(mode="json"),
            "receipt_ref": receipt_ref.model_dump(mode="json"),
            "sample_ref": bundle.sample_bundle_ref.model_dump(mode="json"),
            "propagation_report_ref": bundle.diagnostics["propagation_report_ref"],
            "requested": receipt["requested_draw_count"],
            "attempted": receipt["attempted_draw_count"],
            "successful": receipt["successful_draw_count"],
            "failed": receipt["failed_draw_count"],
            "nominal_point": bundle.point_estimate,
            "credible_interval": bundle.credible_interval,
            "robust_interval": bundle.robust_interval,
            "gate_eligible": receipt["gate_eligible"],
            "draw_summary": report["draw_summary"],
        }
    )
    return fresh, bundle, receipt, samples, ref


@pytest.fixture(scope="module")
def native(tmp_path_factory: pytest.TempPathFactory) -> object:
    return run(tmp_path_factory.mktemp("native-welfare-independent") / "cas")


def test_native_ge_atoms_failed_support_independent_oracle_and_fresh_cas(native: object) -> None:
    fresh, bundle, receipt, samples, ref = native
    # Independent law: P(A=0)=3/4, P(A=1)=1/4. The actual GE inverse
    # (I-A)^-1 multiplies PE response2. A=0 -> welfare2; A=1 -> singular,
    # so no finite unconditional pushforward mean is defined by this evaluator.
    uniforms = np.random.default_rng(31415).random(128)
    indices = [0 if u < 3 / 4 else 1 for u in uniforms]
    if not (sum(indices) == 36):
        raise AssertionError
    if not ([r["sampled_input"]["A"] for r in receipt["sampled_inputs"]] == indices):
        raise AssertionError
    if not ([r["row_index"] for r in receipt["empirical_rows"]] == indices):
        raise AssertionError
    if not (
        (
            receipt["requested_draw_count"],
            receipt["attempted_draw_count"],
            receipt["successful_draw_count"],
            receipt["failed_draw_count"],
            receipt["unattempted_draw_count"],
        )
        == (128, 128, 92, 36, 0)
    ):
        raise AssertionError
    if not ([r["draw_index"] for r in receipt["draw_records"]] == list(range(128))):
        raise AssertionError
    if not (
        {r["draw_index"] for r in receipt["failure_records"]}
        == {i for i, row in enumerate(indices) if row == 1}
    ):
        raise AssertionError
    if not (
        all(
            f["outcome_code"] == "simulation_exception" and f["error_type"] == "LinAlgError"
            for r in receipt["failure_records"]
            for f in r["output_outcomes"]
        )
    ):
        raise AssertionError
    if not (
        samples.welfare_draws == (2.0,) * 92
        and samples.welfare_pe_draws == (2.0,) * 92
        and samples.welfare_ge_draws == (0.0,) * 92
    ):
        raise AssertionError
    if not (samples.metadata["estimate_scope"] == "conditional_on_all_outputs_finite"):
        raise AssertionError
    report = from_canonical_bytes(fresh.get_bytes(bundle.diagnostics["propagation_report_ref"]))
    for key in ("welfare_mean", "welfare_pe_mean", "welfare_ge_mean", "welfare_std"):
        if report["draw_summary"][key] is not None:
            raise AssertionError
    if not (report["draw_summary"]["conditional_welfare_mean"] == 2):
        raise AssertionError
    if not (
        report["draw_summary"]["conditional_welfare_pe_mean"] == 2
        and report["draw_summary"]["conditional_welfare_ge_mean"] == 0
    ):
        raise AssertionError
    if not (
        bundle.credible_interval is None
        and bundle.robust_interval is None
        and receipt["gate_eligible"] is False
    ):
        raise AssertionError
    if "welfare_ge_outer_bound_not_established" not in bundle.warnings:
        raise AssertionError
    if not (bundle.point_estimate == pytest.approx(2 / (1 - 0.25))):
        raise AssertionError  # explicitly distinct deterministic nominal.
    if not (
        receipt["empirical_input_laws"]["A"]["envelope_ref"]["artifact_id"] == str(ref.artifact_id)
    ):
        raise AssertionError


@pytest.mark.parametrize("atom", [1e-15, 1e40])
def test_native_numpy_law_preserves_atoms_end_to_end(tmp_path: Path, atom: object) -> None:
    fresh, bundle, receipt, samples, ref = run(tmp_path / "cas", envelope((0.0, atom), (1.0, 3.0)))
    rows = [0 if u < 0.25 else 1 for u in np.random.default_rng(31415).random(128)]
    inputs = [r["sampled_input"]["A"] for r in receipt["sampled_inputs"]]
    if not (inputs == [0 if row == 0 else atom for row in rows]):
        raise AssertionError
    source = from_canonical_bytes(fresh.get_bytes(ref.artifact_id))
    if not (source["distribution_payload"]["samples"] == [0.0, atom]):
        raise AssertionError
    if not (receipt["failed_draw_count"] == 0 and receipt["support_complete"] is True):
        raise AssertionError
    np.testing.assert_array_equal(samples.welfare_draws, [2 / (1 - x) for x in inputs])
    if bundle.robust_interval is not None:
        raise AssertionError  # varying GE operator, no separate multiplier bound.


def test_exact_cdf_boundaries_zero_mass_and_weight_rescaling() -> None:
    class Rng:
        def __init__(self, u: object) -> None:
            self.u = u

        def random(self) -> object:
            return self.u

    env = envelope((0.0, 1e-15, 0.5), (1.0, 0.0, 3.0))
    law = node._admit_welfare_sampling_laws({"A": env})["A"]
    if not (law.probabilities.tolist() == [0.25, 0.0, 0.75]):
        raise AssertionError
    if not (law.cumulative.tolist() == [0.25, 0.25, 1.0]):
        raise AssertionError
    for u, expected in [
        (0.0, (0, 0.0)),
        (np.nextafter(0.25, 0.0), (0, 0.0)),
        (0.25, (2, 0.5)),
        (np.nextafter(1.0, 0.0), (2, 0.5)),
    ]:
        if not (node._draw_finite_empirical_law(Rng(u), law) == expected):
            raise AssertionError
    scaled = node._admit_welfare_sampling_laws(
        {"A": envelope((0.0, 1e-15, 0.5), (1e300, 0.0, 3e300))}
    )["A"]
    np.testing.assert_array_equal(law.probabilities, scaled.probabilities)
    if not (law.carrier_sha256 != scaled.carrier_sha256):
        raise AssertionError  # same law probabilities, distinct source content.


@pytest.mark.parametrize(
    "defect",
    ["missing_carrier", "unknown_carrier", "zero_mass", "collapsed_mass", "mismatched_family"],
)
def test_individual_bad_law_refuses_before_any_evaluator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    env = envelope()
    if defect == "missing_carrier":
        env = env.model_copy(update={"distribution_payload": None})
    elif defect == "unknown_carrier":
        env = env.model_copy(
            update={"distribution_payload": QuantileSummaryCarrier(quantiles={"0.5": 0.25})}
        )
    elif defect == "zero_mass":
        env = envelope(weights=(0.0, 0.0))
    elif defect == "collapsed_mass":
        env = envelope(weights=(1.0, 1e-320))
    else:
        env = env.model_copy(
            update={
                "distribution_payload": ParametricFitCarrier(
                    family=DistributionFamily.UNIFORM, support=(0.0, 1.0)
                )
            }
        )
    ctx, state, _ = fixture(tmp_path / "cas", env)
    calls = []
    original = node._build_simulation_fn

    def observe(*args: object, **kwargs: object) -> tuple[object, ...]:
        fn, *rest = original(*args, **kwargs)

        def counted(**params: object) -> object:
            calls.append(params)
            return fn(**params)

        return counted, *rest

    monkeypatch.setattr(node, "_build_simulation_fn", observe)
    outcome = node.PropagateWelfareNode().execute(ctx, state)
    if not (outcome.status == "fail" and calls == []):
        raise AssertionError
    if not (outcome.error.code == "ERROR_WELFARE_INPUT_LAW_UNSUPPORTED"):
        raise AssertionError


@pytest.mark.parametrize(
    "defect",
    [
        "weights",
        "axis",
        "digest",
        "row",
        "missing_rows",
        "missing_source_edge",
        "forged_source_kind",
    ],
)
def test_fresh_cas_source_bound_receipt_corruptions(native: object, defect: str) -> None:
    fresh, bundle, original, _, ref = native
    receipt = copy.deepcopy(original)
    manifest = fresh.get_manifest(bundle.diagnostics["draw_outcomes_ref"]["artifact_id"])
    inputs = list(manifest.inputs)
    if defect == "weights":
        receipt["empirical_input_laws"]["A"]["probabilities"] = [0.5, 0.5]
    elif defect == "axis":
        receipt["empirical_input_laws"]["A"]["sample_axis"] = "fake_axis"
    elif defect == "digest":
        receipt["empirical_input_laws"]["A"]["carrier_sha256"] = "0" * 64
    elif defect == "row":
        receipt["empirical_rows"][0]["row_index"] = 1
        receipt["empirical_rows"][0]["row_id"] = (
            receipt["empirical_input_laws"]["A"]["carrier_sha256"] + ":1"
        )
    elif defect == "missing_rows":
        receipt["empirical_rows"].pop()
    elif defect == "missing_source_edge":
        inputs = [x for x in inputs if x.role != "empirical_law:A"]
    else:
        payload = from_canonical_bytes(fresh.get_bytes(ref.artifact_id))
        payload["metadata"]["independent_fake_kind"] = "preserve_all_law_fields"
        false = fresh.put_json(
            payload,
            PutOptions(
                kind="fake.empirical_law",
                media_type="application/json",
                schema=SchemaInfo(name="ir.uncertainty_envelope", version="1.1"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        receipt["empirical_input_laws"]["A"]["envelope_ref"]["artifact_id"] = str(false.artifact_id)
        inputs = [x for x in inputs if x.role != "empirical_law:A"] + [
            node.InputRef(artifact_id=false.artifact_id, role="empirical_law:A")
        ]
    fake = fresh.put_json(
        receipt,
        PutOptions(
            kind="foundry.welfare_draw_outcomes",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.WelfareDrawOutcomes", version="1.0"),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    if not (fresh.verify(fake).ok):
        raise AssertionError
    with pytest.raises(ValueError, match="welfare empirical"):
        node._load_welfare_draw_outcomes(FileSystemCAS(fresh.root), fake)


def test_present_markers_property_removal_accepts_false_weights(
    native: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    fresh, bundle, original, _, _ = native
    receipt = copy.deepcopy(original)
    receipt["empirical_input_laws"]["A"]["probabilities"] = [0.5, 0.5]
    manifest = fresh.get_manifest(bundle.diagnostics["draw_outcomes_ref"]["artifact_id"])
    fake = fresh.put_json(
        receipt,
        PutOptions(
            kind="foundry.welfare_draw_outcomes",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.WelfareDrawOutcomes", version="1.0"),
            inputs=manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    with pytest.raises(ValueError, match="welfare empirical"):
        node._load_welfare_draw_outcomes(FileSystemCAS(fresh.root), fake)
    monkeypatch.setattr(node, "_reconcile_welfare_empirical_rows", lambda *args: None)
    admitted = node._load_welfare_draw_outcomes(FileSystemCAS(fresh.root), fake)
    if not (admitted["empirical_input_laws"]["A"]["probabilities"] == [0.5, 0.5]):
        raise AssertionError


def test_missing_joint_law_retains_only_explicit_nominal_and_zero_stochastic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, state, ref = fixture(tmp_path / "cas")
    state.params["welfare_config"]["input_envelopes"]["B"] = ref.model_dump(mode="json")
    state.params["welfare_config"]["pe_sensitivity"] = {"response": {"B": 1.0}}
    calls = []
    original = node._build_simulation_fn

    def observe(*args: object, **kwargs: object) -> tuple[object, ...]:
        fn, *rest = original(*args, **kwargs)

        def counted(**params: object) -> object:
            calls.append(params)
            return fn(**params)

        return counted, *rest

    monkeypatch.setattr(node, "_build_simulation_fn", observe)
    outcome = node.PropagateWelfareNode().execute(ctx, state)
    if not (outcome.status == "ok"):
        raise AssertionError
    bundle = load_welfare_bundle(
        FileSystemCAS(ctx.store.root), outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]
    )
    receipt = node._load_welfare_draw_outcomes(
        FileSystemCAS(ctx.store.root),
        node.ArtifactRef.model_validate(bundle.diagnostics["draw_outcomes_ref"]),
    )
    if not (calls and all(c == {"A": 0.25, "B": 0.25} for c in calls)):
        raise AssertionError
    # Sensitivity diagnostics may repeat deterministic nominal/finite-difference
    # probes; stochastic support remains zero and carries no uncertainty claim.
    if not (receipt["attempted_draw_count"] == 0 and receipt["unattempted_draw_count"] == 128):
        raise AssertionError
    if not (bundle.credible_interval is None and bundle.robust_interval is None):
        raise AssertionError
    RESULTS.append(
        {
            "test": "missing_joint_law",
            "evaluator_calls": len(calls),
            "nominal_parameter_calls": calls,
            "stochastic_attempts": 0,
            "unattempted": 128,
            "gate_eligible": receipt["gate_eligible"],
        }
    )


def teardown_module() -> None:
    import importlib.metadata as meta

    origins = {
        n: str(Path(m.__file__).resolve())
        for n, m in sys.modules.items()
        if n.startswith("polisyos") and getattr(m, "__file__", None)
    }
    if not (all(Path(p).is_relative_to(Path(os.environ["PYTHONPATH"])) for p in origins.values())):
        raise AssertionError
    Path(os.environ["WELFARE_REVIEW_OUTPUT"]).write_text(
        json.dumps(
            {
                "environment": {
                    "python": sys.version,
                    "executable": sys.executable,
                    "platform": platform.platform(),
                    "numpy": np.__version__,
                    "scipy": meta.version("scipy"),
                    "PYTHONPATH": os.environ["PYTHONPATH"],
                    "backend": "native NumPy GE inverse",
                    "no_artificial_caps": True,
                },
                "source_origin": str(Path(node.__file__).resolve()),
                "source_sha256": hashlib.sha256(Path(node.__file__).read_bytes()).hexdigest(),
                "all_origins_exact": True,
                "polisyos_origin_count": len(origins),
                "results": RESULTS,
            },
            indent=2,
        )
    )
