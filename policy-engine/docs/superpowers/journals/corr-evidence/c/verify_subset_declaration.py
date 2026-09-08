"""Exercise the real pre-call declaration checks without a provider call."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from polisyos.data_forge.domains.academic.batch.abstract_reextraction import (
    _load_declared_works,
    _provider_configuration,
)


def main() -> None:
    """Validate the committed source and provider declarations through their owner."""
    root = Path("docs/superpowers/journals/corr-evidence/c")
    manifest = json.loads((root / "abstract-subset-manifest.json").read_text())
    configuration_path = root / "provider-configuration.json"
    model = json.loads(configuration_path.read_text())["model_id"]
    works = _load_declared_works(manifest)
    configuration = _provider_configuration(configuration_path, manifest, model)
    ids = [work["id"] for work in works]
    if ids != [member["work_id"] for member in manifest["selected_members"]]:
        raise ValueError("declared_selected_identity_mismatch")
    sys.stdout.write(
        json.dumps(
            {
                "status": "validated_before_calls",
                "work_ids": ids,
                "declaration_digest": manifest["declaration_digest"],
                "configuration_digest": configuration["configuration_digest"],
                "provider_calls": 0,
            }
        ) + "\n"
    )


if __name__ == "__main__":
    main()
