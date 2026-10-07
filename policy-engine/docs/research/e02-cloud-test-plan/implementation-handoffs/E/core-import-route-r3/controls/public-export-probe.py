import importlib
import json
import sys
from pathlib import Path

requests = {
    "polisyos.core": ["artifacts", "canon", "registry"],
    "polisyos.ir.analytics": [
        "PosteriorSamplesCarrier",
        "ParametricFitCarrier",
        "load_uncertainty_envelope",
        "persist_uncertainty_envelope",
        "load_forecasting_uncertainty_bundle",
        "persist_forecasting_uncertainty_bundle",
    ],
    "polisyos.foundry.execute": ["get_state_path", "load_state_snapshot", "put_state_snapshot"],
}
rows = []
for module_name, names in requests.items():
    module = importlib.import_module(module_name)
    for name in names:
        try:
            value = getattr(module, name)
        except AttributeError as exc:
            rows.append(
                {
                    "module": module_name,
                    "name": name,
                    "curated": name in module.__all__,
                    "runtime_resolution": "absent",
                    "error": str(exc),
                }
            )
        else:
            rows.append(
                {
                    "module": module_name,
                    "name": name,
                    "curated": name in module.__all__,
                    "runtime_resolution": "present",
                    "definition_module": getattr(
                        value, "__module__", getattr(value, "__name__", None)
                    ),
                }
            )
sys.stdout.write(json.dumps(rows, indent=2) + "\n")
Path("/workspace/e02-E-pr38-r3-receipts/imports-r4/public-export-probe.json").write_text(
    json.dumps(rows, indent=2) + "\n"
)
