from __future__ import annotations

from polisyos.data_forge.kernel.artifacts import (
    ArtifactRef,
    PIILevel,
    ProducerVersion,
    RetentionClass,
)
from polisyos.data_forge.kernel.snapshot.merkle import merkle_root


def _artifact_ref(uri: str, sha256: str) -> ArtifactRef:
    return ArtifactRef(
        uri=uri,
        sha256=sha256,
        producer="tests.unit.data_forge.kernel.snapshot",
        producer_version=ProducerVersion(code_version="1.0.0", lockfile_hash="c" * 64),
        trace_id="1" * 32,
        span_id="2" * 16,
        config_hash="d" * 64,
        owner="team-data-forge",
        license="test-fixture",
        regeneration_command="uv run pytest tests/unit/data_forge/kernel/snapshot/test_merkle.py",
        pii_level=PIILevel.NONE,
        retention_class=RetentionClass.HOT,
        freshness_sla_seconds=3600,
        schema_id="test.schema",
        schema_version="1.0.0",
    )


def test_merkle_root_is_stable_for_same_artifact_set() -> None:
    first = _artifact_ref("polisyos://academic/skg@snap-1", "a" * 64)
    second = _artifact_ref("polisyos://catalog/index@snap-1", "b" * 64)

    assert merkle_root((first, second)) == merkle_root((second, first))


def test_merkle_root_changes_when_artifact_digest_changes() -> None:
    first = _artifact_ref("polisyos://academic/skg@snap-1", "a" * 64)
    changed = _artifact_ref("polisyos://academic/skg@snap-1", "b" * 64)

    assert merkle_root((first,)) != merkle_root((changed,))
