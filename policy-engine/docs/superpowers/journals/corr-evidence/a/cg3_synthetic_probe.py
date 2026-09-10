"""Measure the existing CG3 sibling consumer on explicitly marked source ancestry."""

from __future__ import annotations

import argparse
import faulthandler
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path


def main() -> int:
    """Exercise the real consumer; no generated design or production store is used."""
    faulthandler.dump_traceback_later(60)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record-legacy", type=Path)
    args = parser.parse_args()
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.grounding_admission import GroundingAdmissionEngine
    from tests.unit.runtime.quality.test_grounding_admission import (
        _cg2_novel,
        _novel_transfer_probe,
        _reference,
    )

    source = _reference(include_mechanism=True)
    edges = {
        key: replace(edge, provenance={**edge.provenance, "synthetic": True}).with_content_hash()
        for key, edge in source.essential_edges.items()
    }
    reference = replace(
        source,
        essential_edges=edges,
        reference_hash=gy_content_hash([edge.to_payload() for edge in edges.values()]),
    )
    cg1, cg2 = _cg2_novel(reference, {**_novel_transfer_probe(), "synthetic": True})
    result = GroundingAdmissionEngine(reference).decide(cg2, cg1_certificate=cg1)
    faulthandler.cancel_dump_traceback_later()
    if args.record_legacy is not None:
        if args.record_legacy.exists():
            raise ValueError("legacy_compatibility_control_already_recorded")
        owner_path = Path("src/polisyos/runtime/quality/grounding_admission.py")
        args.record_legacy.parent.mkdir(parents=True, exist_ok=True)
        args.record_legacy.write_text(
            json.dumps(
                {
                    "synthetic": True,
                    "purpose": "synthetic compatibility control from the old producer",
                    "producer_source": str(owner_path),
                    "producer_source_sha256": hashlib.sha256(owner_path.read_bytes()).hexdigest(),
                    "certificate": result.model_dump(mode="json"),
                },
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
    payload = {
        "synthetic": True,
        "purpose": "bounded_closed_CG3_sibling_consumer_measurement",
        "source_all_edge_provenance_marked": all(
            edge.provenance["synthetic"] is True for edge in reference.essential_edges.values()
        ),
        "cg2_synthetic": cg2.synthetic,
        "cg2_decision": cg2.decision,
        "cg3_decision": result.decision,
        "cg3_authority_scope": result.authority_scope,
        "cg3_production_promotable": result.production_promotable,
        "cg3_shadow_patch_emitted": result.registry_patch is not None,
        "status": "fail" if result.production_promotable else "pass",
    }
    sys.stdout.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    return int(result.production_promotable)


if __name__ == "__main__":
    raise SystemExit(main())
