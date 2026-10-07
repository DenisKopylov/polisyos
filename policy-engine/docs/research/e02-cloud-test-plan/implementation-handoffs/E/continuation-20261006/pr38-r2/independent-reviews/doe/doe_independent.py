"Independent bounded Sobol/consumer review; no production-source writes."

from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from fractions import Fraction
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch

import numpy as np

from polisyos.core.artifacts import ArtifactRef, ArtifactWriteOptions, FileSystemCAS, SchemaInfo
from polisyos.core.canon import CanonSpec
from polisyos.scientist.methods.autotune.sensitivity_bridge import SensitivityBridge
from polisyos.scientist.methods.doe import analysis as analysis_module
from polisyos.scientist.methods.doe._receipt import _persist_analysis
from polisyos.scientist.methods.doe.analysis import analyze_sensitivity
from polisyos.scientist.methods.doe.designs import ParameterSpec, SensitivityPlan
from polisyos.scientist.methods.doe.sampling import generate_sensitivity_samples
from polisyos.scientist.methods.search.sensitivity_adapter import SensitivityAwareCandidateGenerator


def _resolve_executable(name: str) -> str:
    (
        "Resolve an admitted executable and refus"  # Exact bound literal continuation.
        "e an unavailable program before invocati"  # Exact bound literal continuation.
        "on."  # Exact bound literal continuation.
    )
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    (
        "Emit the existing CLI text and optionall"  # Exact bound literal continuation.
        "y flush without logging side effects."  # Exact bound literal continuation.
    )
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


ROOT = Path("/workspace/e02-E-doe-20261006")
OUT = Path("/workspace/e02-E-pr38-r2-receipts/independent-cal-reviewer")
SOURCE = "f07b7d485531b96a206ae9b2aad7acf5f2755324"
START = time.monotonic()
CASES = []


def snapshot() -> dict[str, object]:
    names = (
        subprocess.check_output(  # noqa: S603 - source-bound fixture
            [_resolve_executable("git"), "ls-files", "-z", "policy-engine/src"], cwd=ROOT
        )
        .decode()
        .split("\0")
    )
    values = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names if name
    }
    return {
        "file_count": len(values),
        "sha256": hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest(),
        "files": values,
    }


BEFORE = snapshot()
if not (
    subprocess.run(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        [_resolve_executable("git"), "diff", "--quiet", SOURCE, "HEAD", "--", "policy-engine/src"],
        cwd=ROOT,
    ).returncode
    == 0
):
    raise AssertionError
if not (
    subprocess.check_output(  # noqa: S603 - source-bound fixture
        [_resolve_executable("git"), "status", "--porcelain", "--", "policy-engine/src"], cwd=ROOT
    ).decode()
    == ""
):
    raise AssertionError
if not (version("SALib") == "1.5.2"):
    raise AssertionError


def record(name: str, detail: object) -> None:
    item = {"case": name, "outcome": "PASS", "detail": detail}
    CASES.append(item)
    _write_stdout(json.dumps(item, sort_keys=True), flush=True)


def refuses(name: str, callback: object) -> None:
    try:
        callback()
    except ValueError as exc:
        record(name, {"error_type": type(exc).__name__, "message": str(exc)})
        return
    raise AssertionError(f"{name}: invalid request/receipt accepted")


class BaseGenerator:
    def generate(self, history: object, current_best: object, context: object) -> dict[str, object]:
        return {"x": 0.25, "z": 0.75}

    def generate_batch(
        self, history: object, current_best: object, context: object, batch_size: int
    ) -> list[object]:
        return [self.generate(history, current_best, context) for _ in range(batch_size)]


def fake_artifact(
    store: object,
    payload: object,
    *,
    kind: str = "doe_sensitivity_analysis",
    schema: object = "1.0",
) -> object:
    return store.put_json(
        payload,
        ArtifactWriteOptions(
            kind=kind, media_type="application/json", schema=SchemaInfo(name=kind, version=schema)
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def read_consumer(store: object, ref: object) -> object:
    return SensitivityAwareCandidateGenerator.from_artifact(BaseGenerator(), store, ref)


if len(sys.argv) > 1 and sys.argv[1] == "fresh":
    refs = json.loads((OUT / "doe_refs.json").read_text())
    store = FileSystemCAS(OUT / "doe-native-cas")
    for name in ["canonical", "permuted", "morris"]:
        ref = ArtifactRef.model_validate(refs[name])
        consumer = read_consumer(store, ref)
        single = consumer.generate([], None, {})
        batch = consumer.generate_batch([], None, {}, 3)
        if not (single["_sensitivity"] == batch[0]["_sensitivity"]):
            raise AssertionError
        if not (single["_sensitivity"]["analysis_ref"] == ref.model_dump(mode="json")):
            raise AssertionError
        if not (single["_sensitivity"]["authority_purpose"] == "exploratory_parameter_experiment"):
            raise AssertionError
        if not (single["_sensitivity"]["population_law_status"] == "not_established"):
            raise AssertionError
        if not (
            {k: v for k, v in single.items() if k != "_sensitivity"}
            == BaseGenerator().generate([], None, {})
        ):
            raise AssertionError
        record("fresh_consumer_" + name, single["_sensitivity"])
    for name in refs["negative"]:
        ref = ArtifactRef.model_validate(refs["negative"][name])
        if not (store.verify(ref).ok):
            raise AssertionError
        refuses("fresh_content_valid_" + name, lambda ref=ref: read_consumer(store, ref))
    mode = "fresh"
else:
    # Derive the independent ANOVA truth directly from U[0,1] moments.
    def moment(power: object) -> object:
        return Fraction(1, power + 1)

    mean = 2 * moment(1) + 2 * moment(1) ** 2
    second = 2 * moment(2) + 4 * moment(2) ** 2 + 2 * moment(1) ** 2 + 8 * moment(2) * moment(1)
    variance = second - mean**2
    var_x = moment(2) - moment(1) ** 2
    main = 4 * var_x
    interaction = 4 * var_x**2
    if not (variance == 2 * main + interaction == Fraction(25, 36)):
        raise AssertionError
    s1, s2, st = (
        float(main / variance),
        float(interaction / variance),
        float((main + interaction) / variance),
    )
    if not ((s1, s2, st) == (0.48, 0.04, 0.52)):
        raise AssertionError
    record(
        "independent_ANOVA_truth",
        {
            "mean": str(mean),
            "variance": str(variance),
            "main_variance": str(main),
            "interaction_variance": str(interaction),
            "S1": s1,
            "S2": s2,
            "ST": st,
        },
    )

    store = FileSystemCAS(OUT / "doe-native-cas")
    specs = [
        ParameterSpec(name=n, lower_bound=0, upper_bound=1, unit="dimensionless")
        for n in ["x", "z"]
    ]
    plan = SensitivityPlan(
        method="sobol",
        parameter_specs=specs,
        input_law="independent",
        seed=20261007,
        n_trajectories=1024,
        max_estimated_runs=6144,
    )
    samples = generate_sensitivity_samples(plan)
    outputs = samples[:, 0] + samples[:, 1] + 2 * samples[:, 0] * samples[:, 1]
    result = analyze_sensitivity(plan, samples, outputs)
    np.testing.assert_allclose([result.s1["x"], result.s1["z"]], [s1, s1], atol=0.01, rtol=0)
    np.testing.assert_allclose([result.st["x"], result.st["z"]], [st, st], atol=0.01, rtol=0)
    np.testing.assert_allclose(result.s2["x"]["z"], s2, atol=0.01, rtol=0)
    if not (result.top_interactions[0][:2] == ("x", "z")):
        raise AssertionError
    if not (result.total_runs == result.successful_runs == 6144 and result.failed_runs == 0):
        raise AssertionError
    record(
        "native_interaction_oracle",
        {
            "S1": result.s1,
            "S2": result.s2,
            "ST": result.st,
            "runs": result.total_runs,
            "dtype": str(samples.dtype),
        },
    )
    ref = _persist_analysis(store, plan, samples, outputs, result)
    refs = {"canonical": ref.model_dump(mode="json"), "negative": {}}

    block = 6
    order = np.random.default_rng(81209).permutation(plan.n_trajectories)
    perm_x = samples.reshape(-1, block, 2)[order].reshape(-1, 2)
    perm_y = outputs.reshape(-1, block)[order].reshape(-1)
    np.testing.assert_array_equal(
        perm_y, perm_x[:, 0] + perm_x[:, 1] + 2 * perm_x[:, 0] * perm_x[:, 1]
    )
    perm_result = analyze_sensitivity(plan, perm_x, perm_y)
    np.testing.assert_allclose(
        [*perm_result.s1.values(), *perm_result.st.values(), perm_result.s2["x"]["z"]],
        [*result.s1.values(), *result.st.values(), result.s2["x"]["z"]],
        atol=1e-12,
        rtol=0,
    )
    for key in ["ordered_samples_sha256", "ordered_outputs_sha256", "design_id", "analysis_id"]:
        if not (perm_result.metadata[key] != result.metadata[key]):
            raise AssertionError
    record(
        "paired_whole_block_estimands_order_identity",
        {
            "S1": perm_result.s1,
            "S2": perm_result.s2,
            "ST": perm_result.st,
            "old_analysis_id": result.metadata["analysis_id"],
            "new_analysis_id": perm_result.metadata["analysis_id"],
        },
    )
    refuses(
        "old_result_new_paired_order_writer",
        lambda: _persist_analysis(store, plan, perm_x, perm_y, result),
    )
    refs["permuted"] = _persist_analysis(store, plan, perm_x, perm_y, perm_result).model_dump(
        mode="json"
    )

    for name in [
        "duplicate_block",
        "missing_block",
        "interior_roles",
        "wrong_seed",
        "wrong_distribution",
    ]:
        x, y, p = samples.copy(), outputs.copy(), plan
        if name == "duplicate_block":
            x[block : 2 * block], y[block : 2 * block] = x[:block], y[:block]
        elif name == "missing_block":
            x, y = x[:-block], y[:-block]
        elif name == "interior_roles":
            x[[0, 2]], y[[0, 2]] = x[[2, 0]], y[[2, 0]]
        elif name == "wrong_seed":
            p = plan.model_copy(update={"seed": plan.seed + 1})
        else:
            d = plan.model_dump()
            d["parameter_specs"][0].update(
                distribution="triangular",
                distribution_spec={"kind": "triangular", "mode_fraction": 0.3},
            )
            p = SensitivityPlan.model_validate(d)
        refuses(name, lambda x=x, y=y, p=p: analyze_sensitivity(p, x, y))

    original_payload = json.loads(store.get_bytes(ref))
    for name in [
        "stale_paired_order",
        "misaligned_outputs",
        "forged_S2",
        "forged_denominator",
        "wrong_kind",
        "wrong_schema",
        "wrong_purpose",
    ]:
        payload = copy.deepcopy(original_payload)
        kind, schema = "doe_sensitivity_analysis", "1.0"
        if name == "stale_paired_order":
            payload["samples"], payload["outputs"] = perm_x.tolist(), perm_y.tolist()
        elif name == "misaligned_outputs":
            payload["outputs"] = np.roll(outputs, 1).tolist()
        elif name == "forged_S2":
            payload["result"]["s2"]["x"]["z"] = 0.99
        elif name == "forged_denominator":
            payload["result"]["successful_runs"] -= 1
        elif name == "wrong_kind":
            kind = "calibration_report"
        elif name == "wrong_schema":
            schema = "2.0"
        else:
            payload["authority_purpose"] = "causal_effect"
        forged = fake_artifact(store, payload, kind=kind, schema=schema)
        if not (store.verify(forged).ok):
            raise AssertionError
        refs["negative"][name] = forged.model_dump(mode="json")
        refuses(
            "content_valid_" + name,
            lambda forged=forged: read_consumer(FileSystemCAS(store.root), forged),
        )

    with patch.object(analysis_module, "version", lambda distribution: "9.0-review-control"):
        refuses(
            "current_analyzer_version_mismatch",
            lambda: read_consumer(FileSystemCAS(store.root), ref),
        )
    from SALib.analyze import sobol as actual_sobol

    original_analyze = actual_sobol.analyze

    def wrong_current_analyzer(*args: object, **kwargs: object) -> object:
        actual = original_analyze(*args, **kwargs)
        actual["S2"][0, 1] = 0.99
        return actual

    with patch.object(actual_sobol, "analyze", wrong_current_analyzer):
        refuses(
            "current_analyzer_numeric_mismatch",
            lambda: read_consumer(FileSystemCAS(store.root), ref),
        )
        corrupted_result = analyze_sensitivity(plan, samples, outputs)
        if not (abs(corrupted_result.s2["x"]["z"] - s2) > 0.01):
            raise AssertionError
        record(
            "independent_interaction_oracle_detects_property_removal",
            {
                "marker_preserved": corrupted_result.metadata["analyzer"],
                "observed_S2": corrupted_result.s2,
                "oracle_S2": s2,
            },
        )

    calls = []
    bounds = [{"name": n, "lower": 0, "upper": 1, "unit": "dimensionless"} for n in ["x", "z"]]
    for law, seed in [("unknown", 42), ("dependent", 42), ("independent", None)]:
        refuses(
            "pre_evaluator_law_seed_" + str(law) + "_" + str(seed),
            lambda law=law, seed=seed: SensitivityBridge().analyze_search_space(
                bounds, lambda p: calls.append(p) or 0, method="sobol", input_law=law, seed=seed
            ),
        )
        if not (calls == []):
            raise AssertionError
    bridge_calls = []
    answer = SensitivityBridge().analyze_search_space(
        bounds,
        lambda p: bridge_calls.append(p) or (p["x"] + p["z"] + 2 * p["x"] * p["z"]),
        method="sobol",
        input_law="independent",
        seed=plan.seed,
        n_trajectories=1024,
        max_estimated_runs=6144,
        store=store,
    )
    if not (len(bridge_calls) == 6144):
        raise AssertionError
    if not (answer["analysis_ref"] == ref):
        raise AssertionError
    record(
        "actual_bridge_producer_store",
        {
            "evaluator_calls": len(bridge_calls),
            "analysis_ref": answer["analysis_ref"].model_dump(mode="json"),
        },
    )

    morris_bounds = [
        {"name": "x", "lower": 0, "upper": 10, "unit": "metres"},
        {"name": "z", "lower": 0, "upper": 1, "unit": "seconds"},
    ]
    morris = SensitivityBridge().analyze_search_space(
        morris_bounds,
        lambda p: 2 * p["x"] + 3 * p["z"],
        method="morris",
        n_trajectories=8,
        seed=7003,
        store=store,
    )
    np.testing.assert_allclose(
        [morris["result"].mu_star["x"], morris["result"].mu_star["z"]], [20, 3], atol=1e-12, rtol=0
    )
    if not (morris["result"].total_runs == morris["result"].successful_runs == 24):
        raise AssertionError
    refs["morris"] = morris["analysis_ref"].model_dump(mode="json")
    record(
        "bounded_Morris_scale_whole_trajectory_reuse",
        {"mu_star": morris["result"].mu_star, "runs": 24},
    )
    (OUT / "doe_refs.json").write_text(json.dumps(refs, indent=2) + "\n")
    mode = "native"

AFTER = snapshot()
if not (BEFORE == AFTER):
    raise AssertionError("source mutated during independent numerical review")
origins = {
    name: str(Path(module.__file__).resolve())
    for name, module in sys.modules.items()
    if name.startswith("polisyos") and getattr(module, "__file__", None)
}
source_root = ROOT / "policy-engine/src"
if not (all(Path(origin).is_relative_to(source_root) for origin in origins.values())):
    raise AssertionError("mixed polisyos source origins")
environment = {
    "python": sys.version,
    "executable": sys.executable,
    "numpy": np.__version__,
    "SALib": version("SALib"),
    "platform": platform.platform(),
    "thread_caps": {
        k: v for k, v in os.environ.items() if k.endswith("_NUM_THREADS") or k == "XLA_FLAGS"
    },
    "UV_NO_SYNC": os.environ.get("UV_NO_SYNC"),
}
receipt = {
    "source_sha": SOURCE,
    "source_tree": "8dcd5c26a4868e1b055a54a6cd53365e9d5890f3",
    "lane_head": subprocess.check_output(  # noqa: S603 - source-bound fixture
        [_resolve_executable("git"), "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip(),
    "mode": mode,
    "checks": CASES,
    "environment": environment,
    "source_snapshot": {k: v for k, v in BEFORE.items() if k != "files"},
    "source_before_after_identical": True,
    "polisyos_module_count": len(origins),
    "all_polisyos_origins_pinned": True,
    "loaded_analysis_sha256": hashlib.sha256(
        Path(analysis_module.__file__).read_bytes()
    ).hexdigest(),
    "post_import_wall_s": time.monotonic() - START,
}
(OUT / f"doe-{mode}-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
_write_stdout(
    json.dumps(
        {
            "summary": mode,
            "PASS": len(CASES),
            "source_before_after_identical": True,
            "source_sha": SOURCE,
            "post_import_wall_s": receipt["post_import_wall_s"],
        },
        sort_keys=True,
    ),
    flush=True,
)
