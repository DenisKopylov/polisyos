"""Observe the real import guard and unchanged proof-input class/schema identity."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict

from tools.devx.architecture import guardrails


def main() -> int:
    """Run only the import collector and the actual calibration model intake."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-schema-hash")
    args = parser.parse_args()
    policies = guardrails._parse_public_surface(guardrails.DEFAULT_PUBLIC_MANIFEST)
    edges = guardrails.collect_deep_import_edges(policies)
    owned = [asdict(edge) for edge in edges
             if edge.source_module == "polisyos.runtime.quality.grounding_calibration"]
    from polisyos.core import artifacts
    from polisyos.runtime.quality import grounding_calibration as owner

    schema_hash = hashlib.sha256(json.dumps(
        owner.GroundingProofWorldInput.model_json_schema(),
        sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    same_reference_class = (
        owner.GroundingProofWorldInput.model_fields["source_ref"].annotation
        is artifacts.ArtifactRef
    )
    result = {
        "scope": (
            "Actual complete deep-import owner collection, filtered to the assigned source module"
        ),
        "owned_deep_import_findings": owned,
        "reference_is_existing_core_class": same_reference_class,
        "proof_input_schema_hash": schema_hash,
        "expected_schema_hash": args.expected_schema_hash,
        "schema_unchanged": (
            None if args.expected_schema_hash is None else schema_hash == args.expected_schema_hash
        ),
    }
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return int(bool(owned) or not same_reference_class or result["schema_unchanged"] is False)


if __name__ == "__main__":
    raise SystemExit(main())
