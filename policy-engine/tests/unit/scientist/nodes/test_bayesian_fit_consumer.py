"""Real configured method fit -> retained corpus -> CAS -> native uncertainty node."""

from __future__ import annotations

import ast
import base64
import copy
import inspect
import json
import logging
from collections import Counter
from fractions import Fraction

import numpy as np
import pytest

from polisyos.core import artifacts, canon, contracts, registry, run
from polisyos.foundry.uncertainty import BayesianFitBinding, persist_bayesian_fit_envelopes
from polisyos.ir.analytics import admit_posterior_summary_profiles
from polisyos.scientist.compute import JobSpec, run_job
from polisyos.scientist.nodes.builtins.simulate import propagate_uncertainty as node
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_PROPAGATION_REPORT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

FileSystemCAS = artifacts.FileSystemCAS
InputRef = artifacts.InputRef
PutOptions = artifacts.PutOptions
SchemaInfo = artifacts.SchemaInfo
CanonSpec = canon.CanonSpec
content_hash = canon.content_hash
from_canonical_bytes = canon.from_canonical_bytes
to_canonical_bytes = canon.to_canonical_bytes
ExecPlanRef = contracts.foundry.ExecPlanRef
Metrics = contracts.foundry.Metrics
MetricsRef = contracts.foundry.MetricsRef
SimulationResult = contracts.foundry.SimulationResult
build_default_registry_bundle = registry.build_default_registry_bundle
RunContext = run.RunContext


@pytest.fixture(scope="module", params=["hmc", "nuts"])
def real_fit(tmp_path_factory, request):
    root = tmp_path_factory.mktemp("real-bayesian-fit")
    store = FileSystemCAS(root)
    source = {
        "features": [[-2], [0], [2], [-1], [1]],
        "target": [-1, 0, 1, 0, 0],
    }
    refs = {
        name: store.put_json(
            data,
            PutOptions(kind="test.bayesian_source", media_type="application/json"),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        for name, data in source.items()
    }
    params = {
        "runtime_backend": "numpy",
        "num_warmup": 32,
        "num_samples": 32,
        "num_chains": 2,
        "step_size": 0.015,
        "n_leapfrog": 8,
        "credible_mass": 0.9,
    }
    if request.param == "nuts":
        params.pop("n_leapfrog")
        params["max_depth"] = 3
    method_fqn = f"bayesian.sampling.{request.param}@1.0.0"
    # This caller actually materializes the input refs before MethodBackend;
    # a method dispatch spy or a separately supplied input_state is not a witness.
    result = run_job(
        JobSpec(
            job_kind="method",
            method_fqn=method_fqn,
            input_refs=refs,
            method_params=params,
            seed=321,
        ),
        cas_root=root,
    )
    assert not result.issues, result.issues
    assert result.method_result_ref is not None and result.method_evidence_ref is not None
    binding = BayesianFitBinding(
        method_fqn=method_fqn,
        source_refs=refs,
        seed=321,
        effective_parameters={k: v for k, v in params.items() if k != "runtime_backend"},
    )
    raw_result = from_canonical_bytes(store.get_bytes(result.method_result_ref))
    evidence = from_canonical_bytes(store.get_bytes(result.method_evidence_ref))
    return root, store, result, binding, raw_result, evidence


def _copy_pair(tmp_path, real_fit, mutate=None):
    _, original, result, binding, raw_result, evidence = real_fit
    store = FileSystemCAS(tmp_path)
    for ref in binding.source_refs.values():
        store.put_bytes(
            original.get_bytes(ref), PutOptions(kind=ref.kind, media_type=ref.media_type)
        )
    raw_result, evidence = copy.deepcopy(raw_result), copy.deepcopy(evidence)
    if mutate is not None:
        mutate(raw_result, evidence)
    r = store.put_json(
        raw_result,
        PutOptions(
            kind="scientist.method_result.bayesian.sampling",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.MethodResult", version="0.1.0"),
            inputs=[
                InputRef(artifact_id=ref.artifact_id, role=f"input:{name}")
                for name, ref in binding.source_refs.items()
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    # Changing the result bytes requires a new persisted evidence/result link.
    # Individual mutations of that link are applied again below where intended.
    evidence["result_ref"] = str(r.artifact_id)
    e = store.put_json(
        evidence,
        PutOptions(
            kind="scientist.method_evidence",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.MethodExecutionEvidence", version="0.1.0"),
            inputs=[InputRef(artifact_id=r.artifact_id, role="method_result")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return store, r, e, binding


def _rebind_corpus(result, evidence):
    corpus = evidence["artifacts"]["posterior_draws"]
    digest = content_hash(
        to_canonical_bytes(corpus["payload"], CanonSpec(forbid_floats=False)), prefix=True
    )
    virtual = f"artifact://foundry/bayesian/posterior/{digest}"
    corpus.update(artifact_hash=digest, artifact_ref=virtual)
    result["result"]["draws_ref"] = virtual
    result["result"]["draw_layout"] = copy.deepcopy(corpus["payload"]["draw_layout"])
    repro = result["result"]["reproducibility"]
    repro["replay_output_hash"] = digest
    repro["draw_layout"] = copy.deepcopy(corpus["payload"]["draw_layout"])
    evidence["artifacts"]["sampler_reproducibility"] = copy.deepcopy(repro)


def _mutate_supported_profile(result, evidence, case):
    """Change a profile property while retaining complete content/source binding."""
    payload = evidence["artifacts"]["posterior_draws"]["payload"]
    parameters = payload["parameters"]
    repro = result["result"]["reproducibility"]
    if case == "rank4_coefficients":
        parameters["coefficients"]["shape"].append(1)
    elif case == "rank3_intercept":
        parameters["intercept"]["shape"].append(1)
    elif case == "rank3_sigma":
        parameters["sigma"]["shape"].append(1)
    elif case.startswith("missing_parameter_"):
        name = case.removeprefix("missing_parameter_")
        del parameters[name]
        del result["result"]["posterior_means"][name]
    elif case == "extra_parameter":
        parameters["extra_parameter"] = copy.deepcopy(parameters["sigma"])
        result["result"]["posterior_means"]["extra_parameter"] = 0.0
    else:
        outer = case in {"unsupported_versions", "unsupported_top_version", "missing_top_version"}
        inner = case in {
            "unsupported_versions",
            "unsupported_inner_version",
            "missing_inner_version",
        }
        if outer:
            if case == "missing_top_version":
                del repro["contract_version"]
            else:
                repro["contract_version"] = "unsupported.v99"
        if inner:
            if case == "missing_inner_version":
                del repro["determinism_envelope"]["contract_version"]
            else:
                repro["determinism_envelope"]["contract_version"] = "unsupported.v99"
            repro["envelope_id"] = content_hash(
                to_canonical_bytes(repro["determinism_envelope"], CanonSpec(forbid_floats=False)),
                prefix=True,
            )
        if not outer and not inner:
            raise ValueError("unsupported control case")
    _rebind_corpus(result, evidence)


def _node_fixture(store, result_ref, evidence_ref, binding):
    bundle = build_default_registry_bundle(store).bundle_ref
    ctx = ExecutionContext(
        store=store,
        run=RunContext.start(store=store, registry_bundle=bundle, run_id="fit-corpus"),
        logger=logging.getLogger("fit-corpus"),
    )
    metrics = store.put_json(
        Metrics(values={"y": 0.0}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    plan = store.put_json(
        {
            "program_ref": {
                "artifact_id": str(metrics.artifact_id),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    sim = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=plan.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    state = ExperimentState(
        run_id="fit-corpus",
        inputs={
            "bayesian_method_result_ref": result_ref,
            "bayesian_method_evidence_ref": evidence_ref,
        },
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: sim},
        params={
            "posterior_fit": binding.model_dump(mode="json"),
            "propagation_config": {
                "preferred_method": "monte_carlo",
                "mc_n_samples": 256,
                "mc_min_valid_samples": 64,
                "compute_sensitivity": False,
                "mc_sampling_method": "sobol",
                "mc_seed": 42,
                "mc_qmc_scramble": False,
            },
            "propagation_sensitivity": {"y": {"intercept": 1.0, "coefficients": -1.0}},
        },
    )
    return ctx, state


def _values(evidence):
    corpus = evidence["artifacts"]["posterior_draws"]["payload"]
    return {
        name: np.frombuffer(base64.b64decode(record["data_base64"]), dtype="<f8")
        .reshape(record["shape"])
        .reshape(-1)
        for name, record in corpus["parameters"].items()
    }


def _quantile(values, level):
    # Independent exact-ratio empirical inverse CDF; no production reductions.
    ordered = sorted(Fraction.from_float(float(value)) for value in values)
    target = Fraction.from_float(level)
    for i, value in enumerate(ordered, 1):
        if Fraction(i, len(ordered)) >= target:
            return float(value)
    return float(ordered[-1])


def test_real_configured_backend_corpus_persists_and_fresh_node_consumes(real_fit, monkeypatch):
    root, store, result, binding, raw_result, evidence = real_fit
    fresh = FileSystemCAS(root)
    fit = persist_bayesian_fit_envelopes(
        fresh, result.method_result_ref, result.method_evidence_ref, binding
    )
    actual = _values(evidence)
    count = len(actual["intercept"])
    for name, values in actual.items():
        env = fit.envelopes[name]
        mean = float(sum((Fraction.from_float(float(x)) for x in values), Fraction()) / count)
        assert env.metadata["posterior_summary_profile"]["posterior_mean"] == mean
        assert env.point_estimate == _quantile(values, 0.5)
        assert env.confidence_interval == (
            _quantile(values, (1 - 0.9) / 2),
            _quantile(values, 1 - (1 - 0.9) / 2),
        )
        assert tuple(env.distribution_payload.samples) == tuple(values)
        assert env.gate_eligible is False
        assert env.metadata["posterior_summary_profile"]["context"]["parameters"] == {}
        assert {edge.role for edge in fresh.get_manifest(fit.envelope_refs[name]).inputs} == {
            "method_result",
            "method_evidence",
            "features",
            "target",
        }
    assert count == 64
    expected_ids = [f"{fit.corpus_hash}:chain:{c}:draw:{d}" for c in range(2) for d in range(32)]
    assert fit.envelopes["sigma"].metadata["joint_draw_ids"] == expected_ids
    admit_posterior_summary_profiles(fit.envelopes)
    paired = [
        Fraction.from_float(float(a)) - Fraction.from_float(float(b))
        for a, b in zip(actual["intercept"], actual["coefficients"], strict=True)
    ]
    pair_mean = sum(paired, Fraction()) / count
    pair_var = sum(((value - pair_mean) ** 2 for value in paired), Fraction()) / count
    # Centred X and zero-mean y with a symmetric intercept prior imply E[b0]=0.
    # The tiny finite-MCMC tolerance is diagnostic, not a convergence certificate.
    finite_intercept = fit.envelopes["intercept"].metadata["posterior_summary_profile"][
        "posterior_mean"
    ]
    assert abs(finite_intercept) < 0.2
    ctx, state = _node_fixture(
        FileSystemCAS(root), result.method_result_ref, result.method_evidence_ref, binding
    )
    callback_rows = []
    original_build = node._build_propagation_fn

    def traced_build(*args, **kwargs):
        fn, mapped = original_build(*args, **kwargs)

        def traced(**current):
            callback_rows.append(dict(current))
            return fn(**current)

        traced._sensitivity_map = fn._sensitivity_map
        return traced, mapped

    monkeypatch.setattr(node, "_build_propagation_fn", traced_build)
    outcome = node.PropagateUncertaintyNode().execute(ctx, state)
    assert outcome.status == "ok"
    order = sorted(actual)
    expected_rows = Counter(tuple(float(actual[name][i]) for name in order) for i in range(count))
    nominal = tuple(
        fit.envelopes[name].metadata["posterior_summary_profile"]["posterior_mean"]
        for name in order
    )
    observed_rows = Counter(tuple(float(row[name]) for name in order) for row in callback_rows)
    observed_nominal_calls = observed_rows.pop(nominal, 0)
    assert observed_rows == Counter(
        {row: multiplicity * 4 for row, multiplicity in expected_rows.items()}
    )
    assert observed_nominal_calls >= 1
    report_ref = outcome.state.artifacts_index[ARTIFACT_PROPAGATION_REPORT_REF]
    report = from_canonical_bytes(fresh.get_bytes(report_ref))
    assert len(report["bayesian_fit_envelope_refs"]) == 3
    assert report["mapped_params"] == ["coefficients", "intercept"]
    assert {edge.role for edge in fresh.get_manifest(report_ref).inputs} == {
        "input_envelope:coefficients",
        "input_envelope:intercept",
        "input_envelope:sigma",
    }
    print(
        json.dumps(
            {
                "real_backend": evidence["backend"],
                "actual_rows": count,
                "actual_corpus_callback_rows": sum(observed_rows.values()),
                "nominal_callback_count": observed_nominal_calls,
                "corpus_hash": fit.corpus_hash,
                "pair_mean_fraction": str(pair_mean),
                "pair_variance_fraction": str(pair_var),
                "finite_intercept_diagnostic": finite_intercept,
                "diagnostic_tolerance": 0.2,
                "gate_eligible": False,
                "fit_authority": "not_established",
                "fresh_node_status": outcome.status,
                "envelope_refs": report["bayesian_fit_envelope_refs"],
            }
        )
    )


@pytest.mark.parametrize(
    "case",
    [
        "axes",
        "dtype",
        "byte_length",
        "chain_rows",
        "stale_digest",
        "nonfinite",
        "seed",
        "params",
        "source",
        "wrong_pair",
        "kind",
        "duplicate_source",
        "missing_ref",
        "schema",
        "source_view",
        "requested_prior",
        "mixed_group",
        "rank4_coefficients",
        "rank3_intercept",
        "rank3_sigma",
        "missing_parameter_sigma",
        "missing_parameter_intercept",
        "missing_parameter_coefficients",
        "extra_parameter",
        "unsupported_versions",
        "unsupported_top_version",
        "unsupported_inner_version",
        "missing_top_version",
        "missing_inner_version",
    ],
)
def test_adversarial_fit_refuses_before_publication_or_evaluator(
    tmp_path, real_fit, monkeypatch, case
):
    def mutate(result, evidence):
        if case in {
            "rank4_coefficients",
            "rank3_intercept",
            "rank3_sigma",
            "missing_parameter_sigma",
            "missing_parameter_intercept",
            "missing_parameter_coefficients",
            "extra_parameter",
            "unsupported_versions",
            "unsupported_top_version",
            "unsupported_inner_version",
            "missing_top_version",
            "missing_inner_version",
        }:
            _mutate_supported_profile(result, evidence, case)
            return
        payload = evidence["artifacts"]["posterior_draws"]["payload"]
        record = payload["parameters"]["coefficients"]
        if case == "axes":
            payload["draw_layout"]["axis_order"] = ["draw", "chain", "parameter"]
        elif case == "dtype":
            record["dtype"] = "<f4"
        elif case == "byte_length":
            record["data_base64"] = base64.b64encode(b"x").decode()
        elif case == "chain_rows":
            record["shape"] = [1, 64, 1]
        elif case == "stale_digest":
            array = np.frombuffer(base64.b64decode(record["data_base64"]), dtype="<f8").reshape(
                record["shape"]
            )
            record["data_base64"] = base64.b64encode(array[::-1].copy().tobytes()).decode()
        elif case == "nonfinite":
            arr = np.frombuffer(base64.b64decode(record["data_base64"]), dtype="<f8").copy()
            arr[0] = np.nan
            record["data_base64"] = base64.b64encode(arr.tobytes()).decode()
        if case in {"axes", "dtype", "byte_length", "chain_rows", "nonfinite"}:
            _rebind_corpus(result, evidence)

    store, r, e, binding = _copy_pair(tmp_path, real_fit, mutate)
    if case == "seed":
        binding = binding.model_copy(update={"seed": 322})
    elif case == "params":
        binding = binding.model_copy(update={"effective_parameters": {"num_samples": 33}})
    elif case == "source":
        binding = binding.model_copy(
            update={
                "source_refs": dict(reversed(list(binding.source_refs.items())))
                | {"target": binding.source_refs["features"]}
            }
        )
    elif case == "kind":
        r = r.model_copy(update={"kind": "foundry.calibration_report"})
    elif case == "wrong_pair":
        payload = from_canonical_bytes(store.get_bytes(e))
        payload["result_ref"] = str(binding.source_refs["target"].artifact_id)
        e = store.put_json(
            payload,
            PutOptions(
                kind=e.kind,
                media_type=e.media_type,
                schema=SchemaInfo(
                    name="polisyos.scientist.MethodExecutionEvidence", version="0.1.0"
                ),
                inputs=[InputRef(artifact_id=r.artifact_id, role="method_result")],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
    elif case == "schema":
        payload = from_canonical_bytes(store.get_bytes(r))
        manifest = store.get_manifest(r)
        r = store.put_json(
            payload,
            PutOptions(
                kind=r.kind,
                media_type=r.media_type,
                schema=SchemaInfo(name="polisyos.scientist.MethodResult", version="9.9"),
                inputs=manifest.inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
    elif case == "source_view":
        sources = dict(binding.source_refs)
        sources["target"] = sources["target"].model_copy(
            update={"manifest_profile_sha256": "sha256:" + "a" * 64}
        )
        binding = binding.model_copy(update={"source_refs": sources})
    elif case == "requested_prior":
        binding = binding.model_copy(update={"effective_parameters": {"prior_scale": 2.0}})
    elif case == "duplicate_source":
        payload = from_canonical_bytes(store.get_bytes(r))
        manifest = store.get_manifest(r)
        r = store.put_json(
            payload,
            PutOptions(
                kind=r.kind,
                media_type=r.media_type,
                schema=manifest.artifact_schema,
                inputs=[*manifest.inputs, manifest.inputs[0]],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
    ctx, state = _node_fixture(FileSystemCAS(tmp_path), r, e, binding)
    if case == "missing_ref":
        state.inputs.pop("bayesian_method_evidence_ref")
    elif case == "mixed_group":
        from polisyos.scientist.nodes.builtins.state_keys import INPUT_DATA_SNAPSHOT_REF

        fit = persist_bayesian_fit_envelopes(store, r, e, binding)
        snapshot = contracts.fabric.DataSnapshot.model_validate(
            {
                "data_ref": binding.source_refs["target"].model_dump(mode="json"),
                "uncertainty_envelope_ref": fit.envelope_refs["intercept"].model_dump(mode="json"),
            }
        )
        state.inputs[INPUT_DATA_SNAPSHOT_REF] = store.put_json(
            snapshot, PutOptions(kind="fabric.data_snapshot", media_type="application/json")
        )
    calls = 0
    publications = 0
    from polisyos.foundry.uncertainty import PropagationDispatcher

    original_put = FileSystemCAS.put_json

    def counted_put(self, obj, opts, canon_spec=None):
        nonlocal publications
        if opts.kind == "ir.uncertainty_envelope":
            publications += 1
        return original_put(self, obj, opts, canon_spec)

    def forbidden(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("invalid fit reached evaluator")

    monkeypatch.setattr(PropagationDispatcher, "propagate", forbidden)
    monkeypatch.setattr(FileSystemCAS, "put_json", counted_put)
    with pytest.raises(ValueError) as error:
        node.PropagateUncertaintyNode().execute(ctx, state)
    assert calls == publications == 0
    print(
        json.dumps(
            {
                "case": case,
                "evaluator_callbacks": calls,
                "envelope_publications": publications,
                "refusal": str(error.value),
            }
        )
    )


def test_whole_relationship_admission_removal_is_detected(tmp_path, real_fit, monkeypatch):
    bridge = inspect.getmodule(persist_bayesian_fit_envelopes)
    assert bridge is not None

    store, r, e, binding = _copy_pair(tmp_path, real_fit)
    payload = from_canonical_bytes(store.get_bytes(e))
    payload["result_ref"] = str(binding.source_refs["target"].artifact_id)
    e = store.put_json(
        payload,
        PutOptions(
            kind=e.kind,
            media_type=e.media_type,
            schema=SchemaInfo(name="polisyos.scientist.MethodExecutionEvidence", version="0.1.0"),
            inputs=[InputRef(artifact_id=r.artifact_id, role="method_result")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    tree = ast.parse(inspect.getsource(bridge.persist_bayesian_fit_envelopes))
    function = tree.body[0]
    guards = [
        part
        for part in function.body
        if isinstance(part, ast.If)
        and any(
            isinstance(value, ast.Constant)
            and value.value == "Bayesian fit result/evidence/source relationship mismatch"
            for value in ast.walk(part)
        )
    ]
    assert len(guards) == 1
    function.body.remove(guards[0])
    namespace = dict(vars(bridge))
    exec(  # noqa: S102 — compile the inspected local guard-removal control only.
        compile(ast.fix_missing_locations(tree), "relationship-admission-removed", "exec"),
        namespace,
    )
    monkeypatch.setattr(
        node, "persist_bayesian_fit_envelopes", namespace["persist_bayesian_fit_envelopes"]
    )
    ctx, state = _node_fixture(store, r, e, binding)
    outcome = node.PropagateUncertaintyNode().execute(ctx, state)
    assert outcome.status == "ok"  # the independent refusal discriminator fails on this mutant
    print(
        json.dumps(
            {
                "control": "remove_relationship_admission_keep_markers",
                "wrong_pair_admitted": True,
                "node_status": outcome.status,
                "defining_refusal_property": "FAIL",
            }
        )
    )


@pytest.mark.parametrize(
    "case",
    ["rank4_coefficients", "unsupported_versions", "missing_parameter_sigma", "extra_parameter"],
)
def test_supported_profile_admission_removal_is_detected(tmp_path, real_fit, monkeypatch, case):
    bridge = inspect.getmodule(persist_bayesian_fit_envelopes)
    assert bridge is not None
    store, r, e, binding = _copy_pair(
        tmp_path,
        real_fit,
        lambda result, evidence: _mutate_supported_profile(result, evidence, case),
    )
    tree = ast.parse(inspect.getsource(bridge._admit_corpus))
    function = tree.body[0]
    calls = [
        part
        for part in function.body
        if isinstance(part, ast.Expr)
        and isinstance(part.value, ast.Call)
        and isinstance(part.value.func, ast.Name)
        and part.value.func.id == "_admit_supported_profile"
    ]
    assert len(calls) == 1
    function.body.remove(calls[0])
    namespace = dict(vars(bridge))
    exec(  # noqa: S102 — compile the inspected local profile-admission removal only.
        compile(ast.fix_missing_locations(tree), "supported-profile-admission-removed", "exec"),
        namespace,
    )
    monkeypatch.setattr(bridge, "_admit_corpus", namespace["_admit_corpus"])
    ctx, state = _node_fixture(store, r, e, binding)
    outcome = node.PropagateUncertaintyNode().execute(ctx, state)
    assert outcome.status == "ok"
    print(
        json.dumps(
            {
                "case": case,
                "control": "remove_supported_profile_admission",
                "defining_refusal_property": "FAIL",
                "node_status": outcome.status,
            }
        )
    )


@pytest.mark.parametrize("value", [True, float("inf"), "32"])
def test_effective_parameter_profile_rejects_non_real_values_before_store(value):
    with pytest.raises(ValueError):
        BayesianFitBinding(
            method_fqn="bayesian.sampling.hmc@1.0.0",
            source_refs={
                name: {
                    "artifact_id": "sha256:" + "a" * 64,
                    "kind": "test.bayesian_source",
                    "media_type": "application/json",
                }
                for name in ("features", "target")
            },
            seed=321,
            effective_parameters={"num_samples": value},
        )


def test_public_uncertainty_and_calibration_facades_preserve_typed_identity():
    from polisyos.foundry.calibration import (
        BayesianFitBinding as CalibrationBinding,
    )
    from polisyos.foundry.calibration import (
        PersistedBayesianFit as CalibrationFit,
    )
    from polisyos.foundry.calibration import (
        persist_bayesian_fit_envelopes as calibration_persist,
    )
    from polisyos.foundry.uncertainty import PersistedBayesianFit

    assert CalibrationBinding is BayesianFitBinding
    assert CalibrationFit is PersistedBayesianFit
    assert calibration_persist is persist_bayesian_fit_envelopes
