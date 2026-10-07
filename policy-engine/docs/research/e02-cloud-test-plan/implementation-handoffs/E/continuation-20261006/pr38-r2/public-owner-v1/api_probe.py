(
    "Independent facade identity, native CAS/"  # Exact bound literal continuation.
    "snapshot readers, and removed-export con"  # Exact bound literal continuation.
    "trols."  # Exact bound literal continuation.
)

import argparse
import hashlib
import importlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np


def _write_stdout(*values: object, flush: bool = False) -> None:
    (
        "Emit the existing CLI text and optionall"  # Exact bound literal continuation.
        "y flush without logging side effects."  # Exact bound literal continuation.
    )
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


P = argparse.ArgumentParser()
P.add_argument("--phase", required=True)
P.add_argument("--cas-root", type=Path, required=True)
P.add_argument("--mutant", choices=["snapshot-persist-noop", "forecast-persist-noop"])
args = P.parse_args()
ROOT = Path(__file__).parent / "fixture-current" / "policy-engine" / "src"
paths = {}
properties = []


def module(name: str) -> object:
    m = importlib.import_module(name)
    p = Path(m.__file__).resolve()
    if not (p.is_relative_to(ROOT)):
        raise AssertionError((name, p))
    paths[name] = {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    return m


def prop(name: str, claim: object) -> None:
    properties.append({"name": name, "property": claim, "outcome": "PASS"})


def full_origins() -> dict[str, object]:
    rows = []
    for name, m in sorted(sys.modules.items()):
        if name.startswith("polisyos.") and getattr(m, "__file__", None):
            path = Path(m.__file__).resolve()
            if not (path.is_relative_to(ROOT)):
                raise AssertionError((name, path))
            rows.append(
                {
                    "module": name,
                    "path": str(path.relative_to(ROOT)),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    encoded = json.dumps(rows, sort_keys=True).encode()
    out = Path(__file__).parent / (
        args.phase + "-" + (args.mutant or "positive") + "-module-origins.json"
    )
    out.write_text(json.dumps(rows, indent=2) + "\n")
    return {
        "module_count": len(rows),
        "index_sha256": hashlib.sha256(encoded).hexdigest(),
        "full_index_file": str(out),
    }


art = module("polisyos.core.artifacts")
canonical_art = module("polisyos.core.artifacts.store")
man = module("polisyos.core.artifacts.manifest")
if art.FileSystemCAS is not canonical_art.FileSystemCAS:
    raise AssertionError
for n in ("ArtifactRef", "SchemaInfo"):
    if getattr(art, n) is not getattr(man, n):
        raise AssertionError
if art.PutOptions is not canonical_art.PutOptions:
    raise AssertionError
prop(
    "existing-Core-artifact-canonical-identities",
    (
        "curated facade exports canonical store/r"  # Exact bound literal continuation.
        "ef/options/schema, no copied implementat"  # Exact bound literal continuation.
        "ion"  # Exact bound literal continuation.
    ),
)
canon = module("polisyos.core.canon")
codec = module("polisyos.core.canon.canon_json")
if not (
    canon.CanonSpec is codec.CanonSpec and canon.from_canonical_bytes is codec.from_canonical_bytes
):
    raise AssertionError
registry = module("polisyos.core.registry")
loader = module("polisyos.core.registry.loader")
if registry.load_registry_bundle_content is not loader.load_registry_bundle_content:
    raise AssertionError
prop(
    "existing-Core-canon-registry-identities",
    "canonical codec and configured registry loader identities",
)
contracts = module("polisyos.core.contracts")
required = [
    "DataSnapshot",
    "DerivedArtifact",
    "ExecuteRequest",
    "ExecuteResult",
    "FoundryExecConfig",
    "FoundryInputBindingRule",
    "FoundryInputBindings",
    "FoundryInputBindingsRef",
    "SimulationResult",
    "StateSnapshotRef",
]
if not (all(n in contracts.__all__ for n in required)):
    raise AssertionError
ir = module("polisyos.ir")
trinity = module("polisyos.ir.trinity")
if ir.TrinityBundle is not trinity.TrinityBundle:
    raise AssertionError
prop(
    "existing-admitted-Core-contracts-IR-Trinity",
    "all ten BKT contract types declared; root Trinity identity is canonical",
)
store = art.FileSystemCAS(args.cas_root)
payload = {
    "draw_ids": ["d0", "d1", "d2"],
    "rows": [[0, 0], [1, 2], [4, 5]],
    "weights": [0.25, 0.25, 0.5],
}
ref = store.put_json(
    payload,
    art.PutOptions(
        kind="e02.facade-oracle",
        media_type="application/json",
        schema=art.SchemaInfo(name="e02.FacadeOracle", version="1.0.0"),
    ),
    canon_spec=canon.CanonSpec(forbid_floats=False),
)
fresh = art.FileSystemCAS(args.cas_root)
read = canon.from_canonical_bytes(fresh.get_bytes(ref))
if not (read == payload):
    raise AssertionError
prop(
    "configured-Core-CAS-fresh-read",
    (
        "fresh store independently reopens exact artifact bytes prese"
        "rving order/weights; not a new wire contract"
    ),
)
analytics = module("polisyos.ir.analytics")
uncertainty = module("polisyos.ir.analytics.uncertainty")
forecast = module("polisyos.ir.analytics.forecasting_uncertainty")
execution = module("polisyos.foundry.execute")
expected_ir = [
    "PosteriorSamplesCarrier",
    "load_forecasting_uncertainty_bundle",
    "persist_forecasting_uncertainty_bundle",
]
expected_exec = ["get_state_path", "load_state_snapshot", "put_state_snapshot"]
missing_ir = [n for n in expected_ir if n not in analytics.__all__]
missing_exec = [n for n in expected_exec if n not in execution.__all__]
if args.phase == "before-owner-patch":
    if not (missing_ir == expected_ir and missing_exec == expected_exec):
        raise AssertionError
    _write_stdout(
        json.dumps(
            {
                "phase": args.phase,
                "outcome": "PASS-bounded-existing-facades",
                "pending_IR_exports": missing_ir,
                "pending_execute_exports": missing_exec,
                "properties": properties,
                "module_inputs": paths,
                "full_module_origins": full_origins(),
                "owner_admission": "not_ratified",
                "P41": "not_established",
            },
            indent=2,
        )
    )
    sys.exit(0)
if not (not missing_ir and not missing_exec):
    raise AssertionError
core = module("polisyos.core")
for name in (
    "ArtifactRef",
    "ArtifactStore",
    "ArtifactWriteOptions",
    "PutOptions",
    "SchemaInfo",
    "input_ref_from_artifact_ref",
):
    if not (name in core.__all__ and getattr(core, name) is getattr(art, name)):
        raise AssertionError
for name in ("CanonSpec", "from_canonical_bytes"):
    if not (name in core.__all__ and getattr(core, name) is getattr(canon, name)):
        raise AssertionError
if not (
    core.load_registry_bundle_content is registry.load_registry_bundle_content
    and "load_registry_bundle_content" in core.__all__
):
    raise AssertionError
prop(
    "owner-preview-Core-nine-root-identities",
    (
        "nine narrow root exports retain canonical artifacts/canon/re"
        "gistry objects and lazy existing root behavior"
    ),
)
executor = module("polisyos.foundry.execute.executor")
for n in expected_ir:
    if getattr(analytics, n) is not getattr(
        uncertainty if n == "PosteriorSamplesCarrier" else forecast, n
    ):
        raise AssertionError
for n in expected_exec:
    if getattr(execution, n) is not getattr(executor, n):
        raise AssertionError
prop(
    "owner-preview-canonical-exports",
    (
        "three IR analytics and three Foundry execute exports resolve"
        " same canonical objects, existing modes retained"
    ),
)
carrier = analytics.PosteriorSamplesCarrier(
    samples=(0.0, 1.0, 4.0), weights=(0.25, 0.25, 0.5), sample_axis="paired_draw"
)
carrier_read = analytics.PosteriorSamplesCarrier.model_validate_json(carrier.model_dump_json())
if not (carrier_read == carrier):
    raise AssertionError
for values in ({"samples": (0.0, float("inf"))}, {"samples": (0.0, 1.0), "weights": (1.0,)}):
    try:
        analytics.PosteriorSamplesCarrier(**values)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid existing carrier admitted")
prop(
    "existing-carrier-roundtrip-and-refusals",
    (
        "existing v1 carrier values/order/axis/weights survive own re"
        "ader; no authority or joint v2 ratification inferred"
    ),
)
import jax.numpy as jnp  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer
from polisyos.foundry.contracts.state import (  # noqa: E402 - source-bound fixture
    GlobalState,
)
from polisyos.foundry.methods.exceptions import (  # noqa: E402 - source-bound fixture
    StatePathTraversalError,
)

state = GlobalState.empty(3, 2).replace(
    step=jnp.array(7, dtype=jnp.int32),
    tax_rate=jnp.array(0.25, dtype=jnp.float32),
    agents=GlobalState.empty(3, 2).agents.replace(
        income=jnp.array([2.0, 5.0, 11.0], dtype=jnp.float32)
    ),
)
if args.mutant == "snapshot-persist-noop":
    execution.put_state_snapshot = lambda *a, **k: None
snapshot = execution.put_state_snapshot(store, state=state, step=7)
if not (isinstance(snapshot, art.ArtifactRef)):
    raise AssertionError("removed snapshot writer export cannot deliver persisted ref")
reopened = execution.load_state_snapshot(art.FileSystemCAS(args.cas_root), snapshot_ref=snapshot)
np.testing.assert_array_equal(
    execution.get_state_path(reopened, "agents.income"), np.array([2.0, 5.0, 11.0])
)
if not (int(reopened.step) == 7 and float(reopened.tax_rate) == 0.25):
    raise AssertionError
for badpath in ("agents.missing", "agents..income", ""):
    try:
        execution.get_state_path(reopened, badpath)
    except StatePathTraversalError:
        pass
    else:
        raise AssertionError("invalid state path admitted")
try:
    execution.load_state_snapshot(fresh, snapshot_ref=ref)
except ValueError:
    pass
else:
    raise AssertionError("non-snapshot generic payload admitted")
prop(
    "native-snapshot-fresh-consumer",
    (
        "public writer typed2.2 ref→fresh configured CAS→canonical Gl"
        "obalState reader exact step, tax, individual income; invalid"
        " path/non-snapshot refusals"
    ),
)
T = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
bundle = forecast.ForecastingUncertaintyBundle(
    method_fqn="forecasting.univariate.exponential_smoothing@1.0.0",
    target_id="fixture-income",
    generated_at=T,
    prediction_interval=(
        forecast.HorizonInterval(
            horizon=1,
            point=6.0,
            lower=4.0,
            upper=8.0,
            coverage_target=0.9,
            constructor=forecast.ForecastCalibrationMethod.CONFORMAL,
            sample_count=3,
        ),
    ),
    fan_chart=forecast.FanChartSpec(
        quantile_levels=(0.05, 0.5, 0.95),
        horizons=(
            forecast.HorizonQuantileSet(horizon=1, quantiles={".05": 4.0, ".5": 6.0, ".95": 8.0}),
        ),
    ),
    coverage_diagnostic=forecast.ForecastCoverageDiagnostic(
        nominal_coverage=0.9,
        empirical_coverage_by_horizon={1: 2 / 3},
        coverage_gap_by_horizon={1: 2 / 3 - 0.9},
        mean_interval_width_by_horizon={1: 4.0},
        sample_count_by_horizon={1: 3},
        calibration_window=3,
        last_recalibrated_at=T,
    ),
    horizon_policy=forecast.HorizonPolicySpec(
        default_method=forecast.ForecastCalibrationMethod.CONFORMAL,
        rules=(),
        gate_eligible=False,
        summary="bounded export wiring only",
    ),
    interval_semantics=forecast.ForecastIntervalSemantics.CONFORMALIZED_PREDICTION_INTERVAL,
    calibration_method=forecast.ForecastCalibrationMethod.CONFORMAL,
    nominal_coverage=0.9,
    sample_size_assumption="three fixture residuals; no production assertion",
)
if args.mutant == "forecast-persist-noop":
    analytics.persist_forecasting_uncertainty_bundle = lambda *a, **k: None
forecast_ref = analytics.persist_forecasting_uncertainty_bundle(store, bundle)
if not (forecast_ref is not None):
    raise AssertionError("removed forecast writer export cannot deliver persisted ref")
readbundle = analytics.load_forecasting_uncertainty_bundle(
    art.FileSystemCAS(args.cas_root), forecast_ref
)
if not (readbundle == bundle):
    raise AssertionError
if not (
    readbundle.prediction_interval[0].horizon == 1
    and readbundle.prediction_interval[0].point == 6.0
    and not readbundle.horizon_policy.gate_eligible
):
    raise AssertionError
prop(
    "existing-forecast-bundle-fresh-consumer",
    (
        "public canonical functions preserve v1 fixed fixture interva"
        "l/ref through fresh store; gatefalse retained, no v2 semanti"
        "cs chosen"
    ),
)
_write_stdout(
    json.dumps(
        {
            "phase": args.phase,
            "outcome": "PASS-library-preview-only",
            "owner_admission": "not_ratified",
            "properties": properties,
            "module_inputs": paths,
            "full_module_origins": full_origins(),
            "refs": {
                "generic": ref.model_dump(mode="json"),
                "snapshot": snapshot.model_dump(mode="json"),
                "forecast": forecast_ref.model_dump(mode="json"),
            },
            "P41": "not_established",
        },
        indent=2,
    )
)
