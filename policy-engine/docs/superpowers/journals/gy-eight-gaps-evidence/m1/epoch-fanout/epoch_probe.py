"""Exercise current runtime admission using current and genuine historical receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from polisyos.runtime.http.services.acquisition_surface_projection import (
    build_acquisition_growth_projection,
)
from polisyos.runtime.http.services.cycle_board_sources import load_n13b_global_movement_signal
from polisyos.runtime.http.services.governed_projection_validation_worker import (
    validate_acquisition_growth,
)
from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
    read_n13b_acquisition_executor_contract,
    read_n13b_lifecycle_manifest,
)


PATHS = {
    "census": "layer3_gy_n13a_acquisition_census.json",
    "journal": "layer3_gy_n13a_live_probe_journal.json",
    "carrier_liveness": "layer3_gy_n13a_worldbank_government_balance_carrier_liveness.json",
    "executor_contract": "layer3_gy_n13b_acquisition_executor_contract.json",
    "lifecycle_manifest": "layer3_gy_n13b_lifecycle_manifest.json",
    "reentry_trace": "layer3_gy_n13b_reentry_trace.json",
}
PDC = Path("architecture/policy_design_case")


def projection_result(inputs: dict[str, object]) -> dict[str, object]:
    try:
        payload = build_acquisition_growth_projection(**inputs)
        return {
            "accepted": True,
            "admission": payload.n13b_history.admission,
            "world_growth": payload.n13b_history.world_growth,
        }
    except ValueError as exc:
        return {"accepted": False, "reason": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--historical-ref", required=True)
    args = parser.parse_args()
    root = Path.cwd()
    historical_sha = subprocess.check_output(
        ["git", "rev-parse", args.historical_ref], text=True, cwd=root
    ).strip()
    current_inputs = {
        name: json.loads((root / PDC / filename).read_bytes()) for name, filename in PATHS.items()
    }
    current_signal = load_n13b_global_movement_signal(root)
    current = {
        "projection": projection_result(current_inputs),
        "worker_issues": validate_acquisition_growth(root),
        "global_signal": current_signal.model_dump(mode="json"),
    }
    temporary_parent = root / "_build/gy-gaps/m1/epoch-fanout/tmp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    historical_inputs = {}
    with tempfile.TemporaryDirectory(dir=temporary_parent) as temporary:
        historical_root = Path(temporary)
        (historical_root / PDC).mkdir(parents=True)
        bindings = []
        for name, filename in PATHS.items():
            relative = PDC / filename
            if name in {"executor_contract", "lifecycle_manifest"}:
                raw = subprocess.check_output(
                    ["git", "show", f"{historical_sha}:policy-engine/{relative.as_posix()}"],
                    cwd=root,
                )
                bindings.append(
                    {
                        "source": f"policy-engine/{relative.as_posix()}@{historical_sha}",
                        "raw_sha256": hashlib.sha256(raw).hexdigest(),
                    }
                )
            else:
                raw = (root / relative).read_bytes()
            (historical_root / relative).write_bytes(raw)
            historical_inputs[name] = json.loads(raw)
        old_contract = read_n13b_acquisition_executor_contract(
            historical_root / PDC / PATHS["executor_contract"]
        )
        old_lifecycle = read_n13b_lifecycle_manifest(
            historical_root / PDC / PATHS["lifecycle_manifest"]
        )
        historical = {
            "source_bindings": bindings,
            "historical_contract_reader": type(old_contract).__name__,
            "historical_lifecycle_reader": type(old_lifecycle).__name__,
            "projection": projection_result(historical_inputs),
            "worker_issues": validate_acquisition_growth(historical_root),
            "global_signal": load_n13b_global_movement_signal(historical_root).model_dump(
                mode="json"
            ),
        }
    checks = {
        "current_projection_admitted": current["projection"]["accepted"],
        "current_worker_passed": current["worker_issues"] == [],
        "current_global_signal_available": current["global_signal"]["availability"] == "available",
        "historical_projection_refused_at_schema": historical["projection"]
        == {"accepted": False, "reason": "acquisition_growth_source_schema_mismatch"},
        "historical_worker_refused_at_schema": historical["worker_issues"]
        == ["acquisition_growth_source_schema_mismatch"],
        "historical_global_signal_invalid": historical["global_signal"]["availability"]
        == "invalid_source",
        "historical_contract_remains_readable": historical["historical_contract_reader"]
        == "N13bAcquisitionExecutorContractV4",
        "historical_lifecycle_remains_readable": historical["historical_lifecycle_reader"]
        == "N13bLifecycleManifestV2",
    }
    print(
        json.dumps(
            {
                "status": "pass" if all(checks.values()) else "fail",
                "checks": checks,
                "current": current,
                "historical": historical,
            },
            indent=2,
        )
    )
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
