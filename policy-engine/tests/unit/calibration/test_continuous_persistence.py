"""Behavioral controls for reopened continuous pairs, diagnostics, and receipts."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from polisyos.calibration import compute_calibration_curve, evaluate_continuous
from polisyos.calibration.continuous import (
    load_continuous_evaluation,
    persist_continuous_evaluation,
)
from polisyos.core.artifacts import ArtifactWriteOptions, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.foundry.methods.catalog.econometrics.advanced import _summarize_interval_diagnostics
from polisyos.ir.analytics._truthfulness import TruthfulnessReceipt, extract_truthfulness_receipt
from polisyos.ir.analytics.calibration_diagnostics import CalibrationDiagnosticsReport


def _inputs(covered: int = 95) -> tuple[list[float], list[tuple[float, float]]]:
    y = [float(i) for i in range(100)]
    intervals = [(v - 0.1, v + 0.1) for v in y[:covered]] + [(-1000.0, -999.0)] * (100 - covered)
    return y, intervals


def _put(store: FileSystemCAS, payload: object, kind: str, version: str = "1.0"):
    return store.put_json(
        payload,
        ArtifactWriteOptions(
            kind=kind, media_type="application/json", schema=SchemaInfo(name=kind, version=version)
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


@pytest.mark.parametrize("covered", [95, 0])
def test_actual_foundry_summary_persists_and_reopens_exact_pairs(covered: int, tmp_path: Path):
    y, intervals = _inputs(covered)
    store = FileSystemCAS(tmp_path / "cas")
    summary = _summarize_interval_diagnostics(
        y_values=y,
        intervals_by_level={0.95: intervals},
        all_levels=(0.95,),
        nominal_coverage=0.95,
        calibration_store=store,
        source_binding={
            "source": "analytic-ordered-fixture",
            "split": "declared-holdout",
            "horizon": 1,
            "forecast_issued_at": "2026-01-01T00:00:00Z",
            "outcomes_observed_at": "2026-01-02T00:00:00Z",
        },
    )
    reopened = load_continuous_evaluation(FileSystemCAS(store.root), summary["calibration_ref"])
    # Independent numerator: direct comparisons, no curve/report metric helper.
    hits = sum(lo <= value <= hi for value, (lo, hi) in zip(y, intervals, strict=True))
    assert hits == covered
    assert reopened.curves["interval_coverage"][0].mean_observed == hits / len(y)
    assert reopened.metrics.ece == pytest.approx(abs(hits / len(y) - 0.95))
    denominator = reopened.metadata["interval_coverage"]
    assert [denominator[k] for k in ("requested", "eligible", "observed", "missing")] == [
        100,
        100,
        100,
        0,
    ]
    receipt = extract_truthfulness_receipt(reopened)
    assert receipt is not None
    assert receipt.runtime_truthfulness_tier == (
        "approximate_calibrated" if covered == 95 else "unverified"
    )
    assert receipt.evidence_ref is not None
    assert receipt.diagnostics["interval_pairs_basis"] == "recomputed"
    assert receipt.diagnostics["production_source_basis"] == "not_established"
    assert receipt.diagnostics["gate_eligible"] is False


@pytest.mark.parametrize(
    "mutation", ["false_count", "false_coverage", "false_receipt", "outcome", "reorder"]
)
def test_content_valid_fake_result_rejected_after_cas_reopen(mutation: str, tmp_path: Path):
    store = FileSystemCAS(tmp_path / "cas")
    y, intervals = _inputs()
    ref = persist_continuous_evaluation(
        store, evaluate_continuous(y_true=y, intervals={0.95: intervals})
    )
    payload = copy.deepcopy(from_canonical_bytes(store.get_bytes(ref)))
    if mutation == "false_count":
        payload["report"]["metadata"]["interval_coverage"]["eligible"] = 0
    elif mutation == "false_coverage":
        payload["report"]["curves"]["interval_coverage"][0]["mean_observed"] = 1.0
    elif mutation == "false_receipt":
        payload["receipt"]["runtime_truthfulness_tier"] = "exact"
    else:
        from polisyos.core.artifacts import ArtifactRef

        pairs = from_canonical_bytes(
            store.get_bytes(ArtifactRef.model_validate(payload["pairs_ref"]))
        )
        if mutation == "outcome":
            pairs["y_true"][0] = 1e6
        else:
            pairs["intervals"][0].reverse()
        replacement = _put(store, pairs, "continuous_calibration_pairs")
        payload["pairs_ref"] = replacement.model_dump(mode="json")
    fake = _put(store, payload, "continuous_calibration_diagnostics")
    assert store.verify(fake).ok  # Valid hash/schema is deliberately insufficient.
    with pytest.raises(ValueError, match="does not reproduce"):
        load_continuous_evaluation(FileSystemCAS(store.root), fake)


@pytest.mark.parametrize(
    ("kind", "version"), [("wrong_kind", "1.0"), ("continuous_calibration_diagnostics", "9.0")]
)
def test_loader_checks_actual_kind_and_schema(kind: str, version: str, tmp_path: Path):
    store = FileSystemCAS(tmp_path / "cas")
    ref = _put(store, {}, kind, version)
    with pytest.raises(ValueError, match="kind/schema"):
        load_continuous_evaluation(store, ref)


def test_raw_report_positive_receipt_is_not_verified_support():
    y, intervals = _inputs()
    live = evaluate_continuous(y_true=y, intervals={0.95: intervals})
    payload = json.loads(live.model_dump_json())
    payload["truthfulness_receipt"] = live.to_truthfulness_receipt().model_dump(mode="json")
    reopened = CalibrationDiagnosticsReport.model_validate(payload)
    receipt = extract_truthfulness_receipt(reopened)
    assert reopened.truthfulness_receipt is None
    assert receipt is not None and receipt.runtime_truthfulness_tier == "unverified"
    assert "interval_pairs_not_reconciled" in receipt.degradation_reasons


def test_mutated_live_projection_cannot_reuse_private_binding():
    y, intervals = _inputs()
    report = evaluate_continuous(y_true=y, intervals={0.95: intervals})
    report.metadata["interval_coverage"]["eligible"] = 0
    assert report.to_truthfulness_receipt().runtime_truthfulness_tier == "unverified"


def test_model_copy_cannot_install_positive_self_receipt():
    y, intervals = _inputs()
    report = evaluate_continuous(y_true=y, intervals={0.95: intervals})
    copied = report.model_copy(
        update={"truthfulness_receipt": TruthfulnessReceipt(runtime_truthfulness_tier="exact")}
    )
    receipt = extract_truthfulness_receipt(copied)
    assert copied.truthfulness_receipt is None
    assert receipt is not None and receipt.runtime_truthfulness_tier == "approximate_calibrated"
    assert receipt.diagnostics["gate_eligible"] is False


def test_empty_and_incomplete_pair_denominators_survive_persistence(tmp_path: Path):
    store = FileSystemCAS(tmp_path / "cas")
    y, intervals = _inputs()
    for sets, levels, requested, eligible in [
        ([], [], 0, 0),
        ([[], intervals], [0.5, 0.95], 200, 100),
    ]:
        report = evaluate_continuous(y_true=y, intervals=sets, levels=levels)
        ref = persist_continuous_evaluation(store, report)
        reopened = load_continuous_evaluation(store, ref)
        counts = reopened.metadata["interval_coverage"]
        assert (counts["requested"], counts["eligible"], counts["missing"]) == (
            requested,
            eligible,
            requested - eligible,
        )
        assert counts["observed"] == requested
        assert counts["observed_outcomes"] == 100
        assert counts["observed_pairs"] == eligible
        assert counts["missing_outcomes"] == 0
        assert reopened.to_truthfulness_receipt().runtime_truthfulness_tier == "unverified"


def test_seedless_bootstrap_refused_at_persistence(tmp_path: Path):
    y, intervals = _inputs()
    report = evaluate_continuous(
        y_true=y, intervals={0.95: intervals}, uncertainty={"bootstrap": 5}
    )
    with pytest.raises(ValueError, match="explicit replay seed"):
        persist_continuous_evaluation(FileSystemCAS(tmp_path / "cas"), report)


@pytest.mark.parametrize("seed", [None, True, False, 1.0, "1", -1])
def test_present_fake_seed_rejected_before_resampling(seed, monkeypatch):
    import polisyos.calibration.continuous as continuous

    def forbidden_callback(*args, **kwargs):
        raise AssertionError("Bootstrap callback ran before seed admission")

    monkeypatch.setattr(continuous, "_attach_interval_bootstrap", forbidden_callback)
    with pytest.raises(ValueError, match="seed must be a nonnegative integer"):
        evaluate_continuous(
            y_true=[1.0] * 100,
            intervals={0.95: [(0.0, 2.0)] * 100},
            uncertainty={"bootstrap": 5, "seed": seed},
        )


def test_two_dimensional_observations_and_reversed_bounds_refused():
    with pytest.raises(ValueError, match="one-dimensional"):
        evaluate_continuous(y_true=[[1.0, 2.0]], intervals={0.95: [(0.0, 3.0)] * 2})
    with pytest.raises(ValueError, match="lower bound"):
        compute_calibration_curve([1.0], [[(2.0, 0.0)]], levels=[0.95])
