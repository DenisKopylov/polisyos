"""Remove the current-source replay while retaining every emitted marker and ref."""
from __future__ import annotations


import pytest

from polisyos.core import artifacts, canon
from polisyos.runtime.quality import data_forge_binding as owner


def marker_only_readback(*, store, source_artifact_id, catalog, providers=None):
    """Counterfactual: keep typed payload/markers but skip the registered source."""
    del catalog, providers
    payload = owner.FabricMeasurementRootPayload.model_validate(
        canon.from_canonical_bytes(store.get_bytes(artifacts.ArtifactID(source_artifact_id)))
    )
    return owner._fabric_measurement_envelope(payload, source_artifact_id)


def main() -> int:
    print("REMOVAL: real N9 reader keeps source payload, complete problem/spec, hashes and refs;")
    print("resolve_fabric_measurement_root is replaced by typed CAS-only projection.")
    print("The actual recorded source changes after positive admission; the consumer test must fail.")
    owner.resolve_fabric_measurement_root = marker_only_readback
    return pytest.main([
        "-q", "-s",
        "tests/unit/runtime/quality/test_promotion_sequence.py::"
        "test_n9_replays_current_measurement_source_at_admission[source_changed]",
    ])


if __name__ == "__main__":
    raise SystemExit(main())
