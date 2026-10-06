from __future__ import annotations

import hashlib
import inspect
import json
import math
import sys
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
PRODUCT_SRC = REPO / "policy-engine" / "src"
PIN = "198076863e143dea9f89f02734b13d50dae3eed5"
UNCERTAINTY_SOURCE = "policy-engine/src/polisyos/ir/analytics/uncertainty.py"
SCRATCH = Path(__file__).resolve().parent
CAS_ROOT = SCRATCH / "cas-v1_1-roundtrip"
PAYLOAD_PATH = SCRATCH / "baseline_generated_v1_1_payload.json"
RECEIPT_PATH = SCRATCH / "v1_1_replay_receipt.json"
sys.path.insert(0, str(PRODUCT_SRC))

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
import polisyos.ir.analytics.uncertainty as uncertainty_module
from polisyos.ir.analytics.uncertainty import (
    IntervalSemantics,
    UncertaintyEnvelope,
    UncertaintySource,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)
from pydantic import ValidationError

assert Path(uncertainty_module.__file__).resolve() == (
    PRODUCT_SRC / "polisyos" / "ir" / "analytics" / "uncertainty.py"
)
PINNED_SOURCE_BLOB = subprocess.check_output(
    ["git", "rev-parse", f"{PIN}:{UNCERTAINTY_SOURCE}"], cwd=REPO, text=True
).strip()
LOADED_SOURCE_BLOB = subprocess.check_output(
    ["git", "hash-object", str(Path(uncertainty_module.__file__).resolve())],
    cwd=REPO,
    text=True,
).strip()
assert LOADED_SOURCE_BLOB == PINNED_SOURCE_BLOB


def empirical_inverse_cdf(draws: list[int], numerator: int, denominator: int) -> int:
    """Return the discrete empirical inverse-CDF quantile without a statistics library."""

    if not draws or not (0 < numerator <= denominator):
        raise ValueError("invalid quantile request")
    ordered = sorted(draws)
    rank_one_based = (numerator * len(ordered) + denominator - 1) // denominator
    return ordered[rank_one_based - 1]


def main() -> None:
    # Independent oracle: the source criterion fixes the discrete equal-tail values.
    draws = [0] * 99 + [100]
    mean = Fraction(sum(draws), len(draws))
    q05 = empirical_inverse_cdf(draws, 5, 100)
    q95 = empirical_inverse_cdf(draws, 95, 100)
    assert mean == Fraction(1, 1)
    assert (q05, q95) == (0, 0)

    model_schema_default = UncertaintyEnvelope.model_fields["schema_version"].default
    pydantic_schema_id = UncertaintyEnvelope.model_json_schema().get("$id")
    writer_schema_default = inspect.signature(persist_uncertainty_envelope).parameters[
        "schema_version"
    ].default
    assert model_schema_default == "1.1"
    assert writer_schema_default == "1.1"

    # This is a scratch-generated representative v1.1 artifact, not a historical production blob.
    # No summary/quantile estimator is called; a valid old-shape body is persisted and read back.
    store = FileSystemCAS(CAS_ROOT)
    env = UncertaintyEnvelope(
        point_estimate=0.5,
        confidence_interval=(0.0, 0.75),
        confidence_level=0.95,
        source=UncertaintySource.CALIBRATION,
        interval_semantics=IntervalSemantics.CREDIBLE_INTERVAL,
        metadata={"replay_control": "scratch-generated-v1.1"},
    )
    ref = persist_uncertainty_envelope(store, env)
    manifest = store.get_manifest(ref.artifact_id)
    artifact_schema = manifest.artifact_schema
    assert artifact_schema is not None
    assert (manifest.kind, artifact_schema.name, artifact_schema.version) == (
        "ir.uncertainty_envelope",
        "ir.uncertainty_envelope",
        "1.1",
    )
    original_bytes = store.get_bytes(ref.artifact_id)
    PAYLOAD_PATH.write_bytes(original_bytes)

    decoded = UncertaintyEnvelope.model_validate(
        from_canonical_bytes(PAYLOAD_PATH.read_bytes())
    )
    loaded = load_uncertainty_envelope(store, ref)
    assert decoded == env == loaded
    replay_ref = persist_uncertainty_envelope(store, loaded)
    replay_bytes = store.get_bytes(replay_ref.artifact_id)
    assert replay_ref.artifact_id == ref.artifact_id
    assert replay_bytes == original_bytes
    assert hashlib.sha256(replay_bytes).hexdigest() == hashlib.sha256(original_bytes).hexdigest()

    # Current v1.1 containment rule rejects the mathematically valid distinct-functional summary.
    try:
        UncertaintyEnvelope(
            point_estimate=float(mean),
            confidence_interval=(float(q05), float(q95)),
            confidence_level=0.95,
            source=UncertaintySource.CALIBRATION,
            interval_semantics=IntervalSemantics.CREDIBLE_INTERVAL,
        )
    except ValidationError as exc:
        rejection = str(exc)
        assert "must lie within" in rejection
    else:
        raise AssertionError("pinned v1.1 unexpectedly accepted mean 1 with equal-tail [0, 0]")

    result: dict[str, Any] = {
        "pin": "198076863e143dea9f89f02734b13d50dae3eed5",
        "loaded_module": str(Path(uncertainty_module.__file__).resolve()),
        "loaded_source_blob": LOADED_SOURCE_BLOB,
        "oracle": {
            "draw_count": len(draws),
            "mean_fraction": str(mean),
            "equal_tail_q05": q05,
            "equal_tail_q95": q95,
            "quantile_convention": "discrete empirical inverse CDF; left-continuous",
            "numeric_estimator_called": False,
        },
        "v1_1_control": {
            "artifact_id": str(ref.artifact_id),
            "ref_kind": ref.kind,
            "payload_schema_version": decoded.schema_version,
            "manifest_kind": manifest.kind,
            "manifest_schema_name": artifact_schema.name,
            "manifest_schema_version": artifact_schema.version,
            "model_schema_default": model_schema_default,
            "writer_schema_default": writer_schema_default,
            "pydantic_json_schema_id": pydantic_schema_id,
            "byte_exact_model_read_reserialize": original_bytes == replay_bytes,
            "payload_sha256": hashlib.sha256(original_bytes).hexdigest(),
            "payload_path": str(PAYLOAD_PATH.relative_to(REPO)),
            "is_historical_production_artifact": False,
        },
        "v1_1_semantic_control": {
            "expected_rejection": True,
            "mean": 1,
            "interval": [0, 0],
            "reason": rejection,
        },
        "limits": [
            "This verifies a scratch-generated v1.1 body roundtrip on pinned code, not replay of a historical production blob.",
            "No v2 schema/$id was created or tested; only the current v1.1 model/writer defaults and stored manifest identity were checked.",
        ],
    }
    RECEIPT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
