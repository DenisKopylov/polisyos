(
    "Independent configured ForecastOwner exe"  # Exact bound literal continuation.
    "rcising canonical Calibration facade."  # Exact bound literal continuation.
)

import importlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from polisyos import calibration as public
from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.ir.analytics.backtest import load_backtest_report
from polisyos.ir.artifacts import put_json_artifact
from polisyos.ir.registry.refs import ArtifactRefModel


def _write_stdout(*values: object, flush: bool = False) -> None:
    (
        "Emit the existing CLI text and optionall"  # Exact bound literal continuation.
        "y flush without logging side effects."  # Exact bound literal continuation.
    )
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


mode = sys.argv[1]
store_path = Path(sys.argv[2])
source = Path(sys.argv[3]).resolve()
canonical = importlib.import_module("polisyos.calibration.forecast_bridge")
required = (
    "PREDICTIVE_AUTHORITY_DENIALS",
    "REFERENCE_PROFILES",
    "EmpiricalCalibrationContext",
    "EmpiricalCalibrationEvidenceRef",
    "EvidenceArtifactRef",
    "ForecastCalibrationProfile",
    "ForecastCandidateReceipt",
    "ForecastCandidateReceiptRef",
    "load_empirical_calibration_evidence",
    "load_forecast_calibration_profile",
    "persist_empirical_calibration_evidence",
    "persist_forecast_candidate_receipt",
    "produce_empirical_calibration_evidence",
)
if not (set(required) <= set(public.__all__)):
    raise AssertionError
if not (all(getattr(public, n) is getattr(canonical, n) for n in required)):
    raise AssertionError
if mode == "persistence_removed":
    public.persist_empirical_calibration_evidence = lambda *a, **kw: None
from polisyos.scientist.methods.backtesting import (  # noqa: E402 - source-bound fixture
    forecast_owner as owner,
)

if (
    owner.persist_empirical_calibration_evidence
    is not public.persist_empirical_calibration_evidence
):
    raise AssertionError
if (
    owner.produce_empirical_calibration_evidence
    is not public.produce_empirical_calibration_evidence
):
    raise AssertionError

store = FileSystemCAS(store_path)


def put(payload: object, kind: str) -> object:
    return store.put_json(
        payload,
        PutOptions(kind=kind, media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )


training = [3.0 + 2.0 * i for i in range(1, 33)]
holdout = [69.0, 71.0, 73.0]
data = put({"independent_target": training + holdout}, "test.independent.forecast_source")
snapshot = put(DataSnapshot(data_ref=data).model_dump(mode="json"), "fabric.data_snapshot")
rule = put(
    {
        "schema_version": "1.0",
        "rule_id": "rolling-origin-residual-conformal.v1",
        "rule_version": "1.0",
        "estimand": "predictive_interval_coverage",
        "algorithm": "rolling_origin_residual_conformal",
        "nominal_coverage": 0.9,
    },
    "ir.forecast_calibration_rule",
)
model = put({"spec_id": "independent-facade-ets"}, "ir.model_spec")
policy = put({"spec_id": "independent-facade-predictive"}, "ir.policy_spec")
origin = datetime(2026, 2, 1, tzinfo=UTC)
request = owner.ForecastOwnerRequest(
    observed_source_ref=DataSnapshotRef(artifact_id=snapshot.artifact_id),
    split={"train_start": 0, "train_end": 32, "holdout_start": 32, "holdout_end": 35, "horizon": 3},
    target_metric="independent_target",
    method_params={"horizon": 3},
    report_id="independent-facade-report",
    calibration_rule={
        "rule_id": "rolling-origin-residual-conformal.v1",
        "artifact_ref": rule.model_dump(mode="json"),
    },
    temporal_roles=dict(
        zip(
            (
                "data_valid_time",
                "calibration_window_start",
                "calibration_window_end",
                "policy_effective_time",
                "prediction_time",
                "observation_time",
            ),
            (origin + timedelta(days=i) for i in range(6)),
            strict=True,
        )
    ),
    model_spec_ref=model.artifact_id,
    policy_spec_ref=policy.artifact_id,
    seed=41,
)
request_ref = owner.persist_forecast_owner_request(store, request)
profile = public.ForecastCalibrationProfile(
    profile_id="independent-canonical-facade",
    profile_version="1.0",
    request_ref=request_ref,
    calibration_threshold=0.8,
)
profile_ref = ArtifactRefModel.model_validate(
    put_json_artifact(
        store,
        profile.model_dump(mode="json"),
        kind="ir.forecast_calibration_profile",
        schema_name="polisyos.calibration.forecast_calibration_profile",
        schema_version="1.0",
        inputs=[{"artifact_id": str(request_ref.artifact_id), "role": "forecast_request"}],
        canon_spec=CanonSpec(forbid_floats=False),
    )
)
result = owner.ForecastOwner(store, empirical_profile_ref=profile_ref).run(request)
if not (result.empirical_evidence_ref is not None and result.candidate_receipt_ref is not None):
    raise AssertionError
fresh = FileSystemCAS(store_path)
receipt = canonical.load_forecast_candidate_receipt(fresh, result.candidate_receipt_ref)
evidence = public.load_empirical_calibration_evidence(fresh, receipt.empirical_evidence_ref)
report = load_backtest_report(fresh, evidence.report_ref)
rows = report.scenarios[0].outcome_comparisons
if not ([row.y_true for row in rows] == holdout):
    raise AssertionError
# Independent consumer calculation uses the immutable source holdout, not reported counts.
expected_hits = sum(
    lo <= actual <= hi
    for actual, (lo, hi) in zip(holdout, result.predictive_intervals, strict=True)
)
if not (evidence.recomputed_numerator == expected_hits and evidence.recomputed_denominator == 3):
    raise AssertionError
if not (evidence.recomputed_pass_rate == expected_hits / 3):
    raise AssertionError
if not (
    receipt.verifier_provenance == "not_established"
    and receipt.authority_scope == "predictive_only"
    and not report.trust_eligible
):
    raise AssertionError
if not (result.bridge_status == "bridge_pending"):
    raise AssertionError
forged = receipt.model_dump(mode="json") | {"verifier_provenance": "verified"}
try:
    public.ForecastCandidateReceipt.model_validate(forged)
    raise AssertionError("producer candidate fabricated verifier authority")
except ValueError as exc:
    if "verifier_provenance" not in str(exc):
        raise AssertionError from None
origins = {
    n: str(Path(m.__file__).resolve())
    for n, m in sys.modules.items()
    if n.startswith("polisyos.") and getattr(m, "__file__", None)
}
if not (all(Path(p).is_relative_to(source) for p in origins.values())):
    raise AssertionError
_write_stdout(
    json.dumps(
        {
            "mode": mode,
            "training": training,
            "holdout": holdout,
            "seed": 41,
            "actual_point_forecast": result.point_forecast,
            "actual_intervals": result.predictive_intervals,
            "oracle_hits": expected_hits,
            "denominator": 3,
            "candidate_receipt_ref": result.candidate_receipt_ref.model_dump(mode="json"),
            "empirical_evidence_ref": result.empirical_evidence_ref.model_dump(mode="json"),
            "verifier_provenance": receipt.verifier_provenance,
            "authority_scope": receipt.authority_scope,
            "bridge_status": result.bridge_status,
            "input_scope": (
                "synthetic generic facade/caller mechanics; unit/scale/source"
                "-law/served A provenance not established"
            ),
            "module_origins": origins,
        },
        sort_keys=True,
    ),
    flush=True,
)
