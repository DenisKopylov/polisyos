"""Use canonical generator for only the two reviewed facade entrypoints."""
import dataclasses
import json
import sys
from pathlib import Path
sys.path.insert(0,"/workspace/e02-E-continuation-20261006/policy-engine")
from tools.devx.architecture import guardrails as generator

snapshot=json.loads(generator.DEFAULT_PUBLIC_JSON.read_text())
observed={name:dataclasses.asdict(generator._entrypoint_inventory(name)) for name in ("polisyos.calibration","polisyos.foundry.uncertainty")}
expected_counts={"polisyos.calibration":25,"polisyos.foundry.uncertainty":16}
drift={}
for name,entry in observed.items():
    assert entry["facade_mode_observed"]=="eager_exports" and entry["export_count"]==expected_counts[name]
    historical=next(e for p in snapshot["packages"] for e in p["entrypoints"] if e["module"]==name)
    drift[name]={"snapshot_count":historical["export_count"],"actual_count":entry["export_count"],"missing_in_snapshot":sorted(set(entry["exports"])-set(historical["exports"]))}
print(json.dumps({"canonical_generator":str(Path(generator.__file__).resolve()),"scope":"two entrypoints only; no fullglobal guard/check/sync mutation","observed":observed,"snapshot_drift":drift,"next_owner":"E root/topic canonical architecture generator writer with package/API owner review; G integration acceptance","required_companions":["architecture/public_surface/inventory.json","docs/reference/public-surface.md"],"regeneration_recipe":"UV_NO_SYNC=1 uv run --no-sync python tools/devx/architecture/guardrails.py sync --skip-deep-import-baseline"},sort_keys=True),flush=True)
