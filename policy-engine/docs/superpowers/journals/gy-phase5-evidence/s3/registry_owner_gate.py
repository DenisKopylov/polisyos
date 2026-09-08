"""Run the actual frozen-pack registry intake gate and record its observed source closure."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.quality.validation import check_layer3_gy_second_domain_pack as owner


def main() -> None:
    root = Path(__file__).resolve().parents[5]
    bundle = owner._load_frozen_bundle(root)
    paths = set()
    def profile(frame, event, arg):
        if event == "call":
            path = Path(frame.f_code.co_filename)
            if path.is_absolute() and path.is_relative_to(root):
                paths.add(path.relative_to(root).as_posix())
    issues = []
    sys.setprofile(profile)
    try:
        owner._validate_cycle_substrate_registry(root, bundle["census"], bundle["pack"], issues)
    finally:
        sys.setprofile(None)
    changed = set(subprocess.check_output(["git", "diff", "--name-only", "3d572c146", "--", "."],
                                         cwd=root, text=True).splitlines())
    changed = {name.removeprefix("policy-engine/") for name in changed}
    print(json.dumps({"gate": "_validate_cycle_substrate_registry",
        "issues": issues, "observed_executed_python_paths": sorted(paths),
        "slice_changed_paths": sorted(changed), "observed_intersection": sorted(paths & changed),
        "input_closure_status": "not_established",
        "limitation": "Observed Python call paths are complete for this invocation. Native DuckDB, Rust validation, subprocess git and all transitive definition inputs were not independently enumerated; this is not a complete P41 input denominator and cannot establish inherited attribution."}, indent=2))
    assert not issues, "actual_frozen_pack_registry_intake_gate_red"


if __name__ == "__main__":
    main()
