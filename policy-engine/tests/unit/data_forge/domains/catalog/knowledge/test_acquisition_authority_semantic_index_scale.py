"""Bounded structural scale check for Catalog's exact-ref candidate index.

This fixture measures registry descriptor lookup only. Most generated refs are
opaque test metadata and are deliberately not opened as semantic evidence; this
test does not claim that the synthetic corpus establishes meanings, authority,
or the full §6 semantic-definition benchmark denominator.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import artifact_ref_identity_key
from polisyos.core.contracts.variable_binding import (
    VariableRepresentationRef,
    VariableSemanticDefinitionRef,
)
from polisyos.data_forge.domains.catalog.knowledge import acquisition_authority as authority_module
from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    AcquisitionAuthorityEntry,
    _AuthoritySemanticDefinitionIndex,
    build_authority_registry,
)
from tests.unit.data_forge.domains.catalog.knowledge.test_acquisition_authority_model_input_discovery import (
    _authority_entry,
    _model_inputs,
    _resolver,
)

_FIXED_SEED = 20261115
_QUERY_STRATA = 16
_EXACT_BUCKET_SIZE = 4
_WARMUPS = 2
_SAMPLES = 15


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _opaque_definition_ref(label: str) -> VariableSemanticDefinitionRef:
    """Return a deterministic, typed metadata-only ref not stored in CAS."""

    digest = _digest(label)
    return VariableSemanticDefinitionRef.model_validate(
        {
            "artifact_id": str(ArtifactID.from_sha256_hex(digest)),
            "kind": "catalog.variable_semantic_definition",
            "media_type": "application/json",
            "manifest_profile_sha256": f"sha256:{_digest(f'profile:{label}')}",
        }
    )


def _registry_with_fixed_truth_subset(
    authority: Any,
    definition_ref: VariableSemanticDefinitionRef,
    representation_ref: VariableRepresentationRef,
    *,
    row_count: int,
) -> tuple[tuple[AcquisitionAuthorityEntry, ...], tuple[tuple[str, str, str, str | None], ...]]:
    """Build one deterministic descriptor census with a fixed 16-key subset."""

    entries: list[AcquisitionAuthorityEntry] = []
    query_refs: list[VariableSemanticDefinitionRef] = [definition_ref]
    query_refs.extend(
        _opaque_definition_ref(f"seed={_FIXED_SEED}:truth:{index}")
        for index in range(1, _QUERY_STRATA)
    )

    for query_index, query_ref in enumerate(query_refs):
        for candidate_index in range(_EXACT_BUCKET_SIZE):
            entries.append(
                _authority_entry(
                    query_ref,
                    representation_ref,
                    suffix=f"scale-truth-{query_index}-{candidate_index}",
                    dataset_prefix="p07-index-scale",
                )
            )

        # Same artifact bytes under another selected profile are a distinct
        # exact-ref key and must not enter this query's bucket.
        for alias_index in range(2):
            alias_ref = query_ref.model_copy(
                update={
                    "manifest_profile_sha256": (
                        f"sha256:{_digest(f'alias:{query_index}:{alias_index}:{_FIXED_SEED}')}"
                    )
                }
            )
            entries.append(
                _authority_entry(
                    alias_ref,
                    representation_ref,
                    suffix=f"scale-profile-alias-{query_index}-{alias_index}",
                    dataset_prefix="p07-index-scale",
                )
            )

    while len(entries) < row_count:
        index = len(entries)
        distractor_ref = _opaque_definition_ref(f"seed={_FIXED_SEED}:unrelated:{index}")
        entries.append(
            _authority_entry(
                distractor_ref,
                representation_ref,
                suffix=f"scale-distractor-{index}",
                dataset_prefix="p07-index-scale",
            )
        )

    assert len(entries) == row_count
    query_keys = tuple(artifact_ref_identity_key(ref) for ref in query_refs)
    registry = build_authority_registry(
        baseline_content_sha256=authority.provision.baseline_content_sha256,
        l5_measurement_registry_sha256=(authority.provision.l5_measurement_registry_content_sha256),
        entries=tuple(entries),
    )
    return registry.entries, query_keys


def _exhaustive_exact_ref_oracle(
    entries: tuple[AcquisitionAuthorityEntry, ...],
    definition_key: tuple[str, str, str, str | None],
) -> tuple[AcquisitionAuthorityEntry, ...]:
    """Independently scan every registry entry by the full selected ref key."""

    return tuple(
        entry
        for entry in entries
        if entry.source_semantic_definition_ref is not None
        and artifact_ref_identity_key(entry.source_semantic_definition_ref) == definition_key
    )


def _percentile(values: list[float], percentile: int) -> float:
    ordered = sorted(values)
    rank = max(1, (len(ordered) * percentile + 99) // 100)
    return ordered[min(rank - 1, len(ordered) - 1)]


def _time_lookup(
    operation: Callable[[tuple[str, str, str, str | None]], object],
    query_keys: tuple[tuple[str, str, str, str | None], ...],
) -> tuple[float, ...]:
    elapsed: list[float] = []
    for _ in range(_WARMUPS):
        for key in query_keys:
            operation(key)
    for _ in range(_SAMPLES):
        for key in query_keys:
            started = time.perf_counter_ns()
            operation(key)
            elapsed.append((time.perf_counter_ns() - started) / 1_000_000)
    return tuple(elapsed)


@pytest.mark.parametrize("row_count", [1_000, 10_000], ids=("1k", "10k"))
def test_exact_index_matches_independent_scan_as_registry_grows(
    tmp_path: Path,
    row_count: int,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    """Compare exact indexed candidate sets against a full scan at 10x size.

    The fixed seed, 16 query keys, four exact candidates per key, two
    wrong-profile near misses per key, 2 warmups, and 15 samples are held
    constant between corpus sizes. Timings are descriptive local baselines;
    they are not a p99 service-level threshold. The synthetic distractor refs
    are not dereferenced and do not count as semantically verified definitions.
    """

    from polisyos.core.artifacts.store import FileSystemCAS

    store = FileSystemCAS(tmp_path / "cas")
    definition_ref, representation_ref, _, _ = _model_inputs(store)
    base_entry = _authority_entry(definition_ref, representation_ref)
    authority, _ = _resolver(
        tmp_path / "catalog-owner",
        authority_entry=base_entry,
    )
    entries, query_keys = _registry_with_fixed_truth_subset(
        authority,
        definition_ref,
        representation_ref,
        row_count=row_count,
    )
    registry = build_authority_registry(
        baseline_content_sha256=authority.provision.baseline_content_sha256,
        l5_measurement_registry_sha256=(authority.provision.l5_measurement_registry_content_sha256),
        entries=entries,
    )

    # Measure the real Catalog owner's cold build/first lookup separately.
    authority._semantic_definition_index_cache = None
    cold_started = time.perf_counter_ns()
    first_candidates = authority._source_entries_for_semantic_definition(
        registry,
        query_keys[0],
    )
    cold_build_ms = (time.perf_counter_ns() - cold_started) / 1_000_000
    index = authority._semantic_definition_index_cache
    assert index is not None and index.is_complete
    assert index.registry_content_sha256 == registry.content_sha256
    assert first_candidates == _exhaustive_exact_ref_oracle(entries, query_keys[0])

    for key in query_keys:
        indexed = authority._source_entries_for_semantic_definition(registry, key)
        exhaustive = _exhaustive_exact_ref_oracle(entries, key)
        assert indexed == exhaustive
        assert len(indexed) == _EXACT_BUCKET_SIZE

    indexed_ms = _time_lookup(
        lambda key: authority._source_entries_for_semantic_definition(registry, key),
        query_keys,
    )
    exhaustive_ms = _time_lookup(
        lambda key: _exhaustive_exact_ref_oracle(entries, key),
        query_keys,
    )
    indexed_rows_returned = sum(
        len(authority._source_entries_for_semantic_definition(registry, key)) for key in query_keys
    )
    exhaustive_rows_examined = row_count * len(query_keys)
    assert indexed_rows_returned == _QUERY_STRATA * _EXACT_BUCKET_SIZE
    assert index.eligible_entry_count == row_count
    assert len(
        {
            artifact_ref_identity_key(entry.source_semantic_definition_ref)
            for entry in entries
            if entry.source_semantic_definition_ref is not None
        }
    ) == row_count - (_QUERY_STRATA * (_EXACT_BUCKET_SIZE - 1))

    # A stale snapshot must rebuild before lookup; an incomplete index returned
    # by the builder must take the real exhaustive fallback path.
    authority._semantic_definition_index_cache = _AuthoritySemanticDefinitionIndex(
        registry_content_sha256="0" * 64,
        entries_by_definition={},
        indexed_entry_count=0,
        eligible_entry_count=0,
    )
    rebuilt_candidates = authority._source_entries_for_semantic_definition(
        registry,
        query_keys[0],
    )
    assert rebuilt_candidates == _exhaustive_exact_ref_oracle(entries, query_keys[0])
    assert authority._semantic_definition_index_cache is not None
    assert authority._semantic_definition_index_cache.is_complete
    assert authority._semantic_definition_index_cache.registry_content_sha256 == (
        registry.content_sha256
    )

    incomplete = _AuthoritySemanticDefinitionIndex(
        registry_content_sha256=registry.content_sha256,
        entries_by_definition={},
        indexed_entry_count=0,
        eligible_entry_count=row_count,
    )
    authority._semantic_definition_index_cache = None
    monkeypatch.setattr(
        authority_module,
        "_build_authority_semantic_definition_index",
        lambda _: incomplete,
    )
    fallback_candidates = authority._source_entries_for_semantic_definition(
        registry,
        query_keys[0],
    )
    assert not incomplete.is_complete
    assert fallback_candidates == _exhaustive_exact_ref_oracle(entries, query_keys[0])

    report = {
        "seed": _FIXED_SEED,
        "descriptor_rows": row_count,
        "unique_definition_ref_keys": len(
            {
                artifact_ref_identity_key(entry.source_semantic_definition_ref)
                for entry in entries
                if entry.source_semantic_definition_ref is not None
            }
        ),
        "query_keys": len(query_keys),
        "exact_bucket_size_each": _EXACT_BUCKET_SIZE,
        "truth_subset_rows": _QUERY_STRATA * _EXACT_BUCKET_SIZE,
        "near_miss_wrong_profile_rows": _QUERY_STRATA * 2,
        "warmups_per_operation": _WARMUPS,
        "samples_per_operation": _SAMPLES,
        "indexed_rows_returned_total": indexed_rows_returned,
        "exhaustive_rows_examined_total": exhaustive_rows_examined,
        "semantic_cas_reads": 0,
        "proof_reads": 0,
        "cold_build_and_first_lookup_ms": cold_build_ms,
        "indexed_ms": {
            "p50": statistics.median(indexed_ms),
            "p95": _percentile(list(indexed_ms), 95),
            "p99": _percentile(list(indexed_ms), 99),
        },
        "exhaustive_ms": {
            "p50": statistics.median(exhaustive_ms),
            "p95": _percentile(list(exhaustive_ms), 95),
            "p99": _percentile(list(exhaustive_ms), 99),
        },
        "timing_status": "descriptive_local_baseline_no_sla_claim",
        "semantic_status": "metadata_only_unselected_refs_not_opened",
        "stale_index_rebuild_matches_exhaustive": True,
        "incomplete_index_fallback_matches_exhaustive": True,
    }
    record_property("p07_index_scale_report", json.dumps(report, sort_keys=True))
    print("P07_INDEX_SCALE " + json.dumps(report, sort_keys=True))
