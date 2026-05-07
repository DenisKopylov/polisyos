from __future__ import annotations

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from polisyos.data_forge.kernel.artifacts import (
    ArtifactRef,
    PIILevel,
    ProducerVersion,
    RetentionClass,
)
from polisyos.data_forge.kernel.snapshot import merkle_root


_HEX64 = st.text("0123456789abcdef", min_size=64, max_size=64)


def _artifact_ref(index: int, *, sha256: str, snapshot: int) -> ArtifactRef:
    return ArtifactRef(
        uri=f"polisyos://property/artifact_{index}@snap-{snapshot}",
        sha256=sha256,
        producer="tests.property.data_forge",
        producer_version=ProducerVersion(code_version="1.0.0", lockfile_hash="c" * 64),
        trace_id=f"{index:032x}"[-32:],
        span_id=f"{index:016x}"[-16:],
        config_hash="d" * 64,
        owner="team-data-forge",
        license="test-fixture",
        regeneration_command="uv run pytest tests/property/data_forge",
        pii_level=PIILevel.NONE,
        retention_class=RetentionClass.HOT,
        freshness_sla_seconds=3600,
        schema_id="property.schema",
        schema_version="1.0.0",
    )


@st.composite
def _artifact_refs(draw: st.DrawFn) -> tuple[ArtifactRef, ...]:
    count = draw(st.integers(min_value=0, max_value=10))
    digests = draw(st.lists(_HEX64, min_size=count, max_size=count))
    snapshots = draw(
        st.lists(
            st.integers(min_value=0, max_value=10_000),
            min_size=count,
            max_size=count,
        )
    )
    return tuple(
        _artifact_ref(index, sha256=digest, snapshot=snapshot)
        for index, (digest, snapshot) in enumerate(zip(digests, snapshots, strict=True))
    )


@given(refs=_artifact_refs())
@settings(max_examples=100)
def test_merkle_root_is_order_independent_and_sha256_shaped(
    refs: tuple[ArtifactRef, ...],
) -> None:
    root = merkle_root(refs)

    assert root == merkle_root(tuple(reversed(refs)))
    assert re.fullmatch(r"[0-9a-f]{64}", root)
