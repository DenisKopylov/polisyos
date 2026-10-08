# S1 bounded discriminators

Source: `f00dd7661a8d3329fb1fa1b049decb0d1d2f277b`; unchanged production/test files.

LA-032 probe below reads synthetic bytes only. Run with the source checkout on
PYTHONPATH and a scratch fixture root. Root execution replaced TemporaryDirectory
with a retained directory under ignored `_build`, so fixture cleanup did not
permanently delete data. Complete output is `la032-stdout.txt`. The observed
mixed-layout sibling acceptance is a counterexample, not a positive source admission.

```python
"""Read-only synthetic discriminator for LA-032's four Ukraine readers.

This probe creates a temporary fixture, imports the existing public read_api,
and prints only synthetic source aliases and acceptance outcomes. It does not
read production inputs or modify repository source or tests.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from polisyos.data_forge.read_api.ukraine import (
    load_demography_artifacts,
    load_donor_pool,
    load_reconciled_targets,
    load_transition_priors,
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="l01-s1-la032-") as temp_root:
        root = Path(temp_root)
        _write_json(
            root / "demography" / "targets.json",
            {
                "state_ids": ["probe-state"],
                "target_state_totals": [1.0],
                "entrant_state_totals": [0.0],
                "metadata": {"probe_origin": "new_targets"},
            },
        )
        _write_json(
            root / "demography_transition_priors.json",
            {
                "transition_prior_matrix": [[1.0]],
                "metadata": {"probe_origin": "legacy_priors"},
            },
        )
        _write_json(
            root / "demography_donor_pool.json",
            {
                "donor_weights": [1.0],
                "donor_state_index": [0],
                "donor_record_index": [1],
                "metadata": {"probe_origin": "legacy_donor"},
            },
        )

        siblings = {
            "targets": load_reconciled_targets(root)["metadata"]["probe_origin"],
            "priors": load_transition_priors(root)["metadata"]["probe_origin"],
            "donor": load_donor_pool(root)["metadata"]["probe_origin"],
        }
        try:
            load_demography_artifacts(root)
        except ValueError:
            composite = "refused_mixed_layout"
        else:
            composite = "accepted"

        result = {
            "fixture": "synthetic_only",
            "sibling_reader_origins": siblings,
            "composite_reader": composite,
            "property_under_probe": "all_four_readers_require_one_admitted_versioned_inventory",
        }
        assert siblings == {
            "targets": "new_targets",
            "priors": "legacy_priors",
            "donor": "legacy_donor",
        }
        assert composite == "refused_mixed_layout"
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
```

LA-036 maintained commands are in `inventory.json#/checks`. The two cases prove
that the requested conditional alias shares the effective KernelSHAP calculation
and does not create an independent method. Their PASS is not a conditional-law
PASS. The actual observed-feature conditional law/model/support/epoch and
C09/C08 supplier are not established; C10/C11 must perform fresh law verification
and matched removal after that supplier exists.
