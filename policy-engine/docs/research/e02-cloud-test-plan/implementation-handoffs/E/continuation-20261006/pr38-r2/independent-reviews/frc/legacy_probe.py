"""Create v1 evidence on exact source; reopen unchanged on the candidate."""

import argparse
import json
import runpy
import sys
from pathlib import Path

from polisyos.calibration.forecast_bridge import load_forecast_candidate_receipt
from polisyos.core.artifacts import FileSystemCAS
from polisyos.ir.artifacts import get_json_artifact
from polisyos.scientist.methods.backtesting.forecast_owner import ForecastOwner


def _write_stdout(*values: object, flush: bool = False) -> None:
    """Emit the existing CLI text and optionally flush without logging side effects."""
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


parser = argparse.ArgumentParser()
parser.add_argument("--cas", type=Path, required=True)
parser.add_argument("--helper", type=Path)
args = parser.parse_args()
store = FileSystemCAS(args.cas)
ref_file = args.cas.parent / "legacy-candidate-ref.json"
if args.helper:
    helper = runpy.run_path(str(args.helper))
    request, profile = helper["_configured"](store, [31.0, 32.0, 33.0, 34.0])
    result = ForecastOwner(store, empirical_profile_ref=profile).run(request)
    ref_file.write_text(json.dumps(result.candidate_receipt_ref.model_dump(mode="json")))
    _write_stdout(
        json.dumps(
            {
                "stage": "legacy-producer",
                "request_version": get_json_artifact(
                    store,
                    get_json_artifact(store, result.candidate_receipt_ref.artifact_id)[
                        "request_ref"
                    ]["artifact_id"],
                ).get("schema_version", "1.0"),
                "candidate_ref": json.loads(ref_file.read_text()),
                "denominator": result.coverage_denominator,
            }
        )
    )
else:
    receipt = load_forecast_candidate_receipt(store, json.loads(ref_file.read_text()))
    _write_stdout(
        json.dumps(
            {
                "stage": "candidate-legacy-read",
                "candidate_ref": json.loads(ref_file.read_text()),
                "verifier_provenance": receipt.verifier_provenance,
                "authority_scope": receipt.authority_scope,
                "outcome": "PASS",
            }
        )
    )
