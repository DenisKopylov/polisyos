"""Opt-in real-CAS semantic corpus profiles for Catalog's exact-ref index.

The ordinary profile covers 1,000 records. Separate explicit opt-in profiles
cover 10,000 and 30,000 records; none establishes the full 100k/300k §6 scale
suite or an operational performance gate. Every definition and representation
is a real, typed, content-addressed test artifact. Synthetic fixture evidence
establishes only that these declared records can be reopened and validated; it
establishes no empirical meaning, source authority, currentness, or permission.
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from threading import Barrier, Event, get_ident

import pytest

from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactRef,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
    write_bytes_atomic,
)
from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    ProducerInfo,
    SchemaInfo,
    artifact_ref_identity_key,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.variable_binding import (
    SelectedVariableBindingRef,
    VariableRepresentation,
    VariableRepresentationRef,
    VariableSemanticDefinition,
    VariableSemanticDefinitionRef,
    load_variable_representation,
    variable_representation_manifest_inputs,
)
from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    AcquisitionAuthorityEntry,
    AcquisitionAuthorityRegistry,
    AcquisitionSourceMeasureScope,
    AuthoritySchemaColumn,
    _AuthoritySemanticDefinitionIndex,
    build_authority_entry,
    build_authority_registry,
)
from tests._helpers.acquisition_production import _entry, _resolver

_RECORDS = 1_000
_MEDIUM_PROFILE_RECORDS = 10_000
_LARGE_PROFILE_RECORDS = 30_000
_PROFILE_ENV = "POLICYOS_P07_SEMANTIC_CORPUS_PROFILE"
_TRUTH_KEYS = 16
_ALTERNATIVES_PER_TRUTH_KEY = 4
_NEAR_MISS_REVISIONS = 16
_SEED = 20261115
_MAX_SCRATCH_BYTES = 256 * 1024 * 1024
_OPT_IN_SCRATCH_BYTES = 2 * 1024 * 1024 * 1024
# Prior admitted local P07 profile cap; this is a runner-safety envelope, not a deployment SLO.
_PROFILE_MAX_WALL_SECONDS = 1200
_PROFILE_MAX_PROCESS_TREE_RSS_BYTES = 5 * 1024 * 1024 * 1024
_WARMUPS = 2
_SAMPLES = 15
_DOMAINS = (
    "public.health",
    "public.transport",
    "public.education",
    "public.climate",
)
pytestmark = pytest.mark.benchmark


def _put_definition(
    store: FileSystemCAS,
    *,
    evidence_ref: ArtifactRef,
    namespace: str,
    stable_id: str,
    revision: str,
    meaning: str,
    producer: ProducerInfo | None = None,
) -> VariableSemanticDefinitionRef:
    """Persist one actual typed semantic definition with fixture-only evidence."""
    selected_evidence_ref = SelectedVariableBindingRef.model_validate(
        evidence_ref.model_dump(mode="json")
    )
    definition = VariableSemanticDefinition(
        namespace=namespace,
        stable_id=stable_id,
        revision=revision,
        meaning=meaning,
        definition_evidence_refs=(selected_evidence_ref,),
    )
    ref = store.put_json(
        definition,
        PutOptions(
            kind=definition.ARTIFACT_KIND,
            media_type=definition.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=definition.ARTIFACT_SCHEMA_NAME,
                version=definition.ARTIFACT_SCHEMA_VERSION,
            ),
            producer=producer,
            inputs=[input_ref_from_artifact_ref(selected_evidence_ref, role="definition_evidence")],
        ),
        return_selected_profile=True,
    )
    return VariableSemanticDefinitionRef.model_validate(ref.model_dump(mode="json"))


def _put_representation(
    store: FileSystemCAS,
    *,
    semantic_ref: VariableSemanticDefinitionRef,
    representation_id: str,
    revision: str,
    quantity_kind: str,
    measure_form: str,
    unit_id: str,
    time_support: str,
    temporal_granularity: str = "annual",
    numerator_ref: VariableSemanticDefinitionRef | None = None,
    denominator_ref: VariableSemanticDefinitionRef | None = None,
) -> VariableRepresentationRef:
    """Persist one real representation whose owner-bound definition ref is exact."""
    representation = VariableRepresentation(
        representation_id=representation_id,
        revision=revision,
        semantic_definition_ref=semantic_ref,
        quantity_kind=quantity_kind,
        measure_form=measure_form,
        unit_id=unit_id,
        scale_to_unit=Decimal("1"),
        numerator_ref=numerator_ref,
        denominator_ref=denominator_ref,
        time_support=time_support,
        temporal_granularity=temporal_granularity,
        aggregation="sum",
        grain=("population", "period"),
        population_ref="population:test-owned",
    )
    ref = store.put_json(
        representation,
        PutOptions(
            kind=representation.ARTIFACT_KIND,
            media_type=representation.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=representation.ARTIFACT_SCHEMA_NAME,
                version=representation.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=list(variable_representation_manifest_inputs(representation)),
        ),
        return_selected_profile=True,
    )
    return VariableRepresentationRef.model_validate(ref.model_dump(mode="json"))


def _definition_identity(ref: VariableSemanticDefinitionRef) -> tuple[str, str, str, str | None]:
    """Build the exact selected-ref identity independently of the Catalog index."""
    return (
        str(ref.artifact_id),
        ref.kind,
        ref.media_type,
        ref.manifest_profile_sha256,
    )


def _entry_for_record(
    definition_ref: VariableSemanticDefinitionRef,
    representation_ref: VariableRepresentationRef,
    *,
    namespace: str,
    stable_id: str,
    suffix: str,
    population: str,
    time_scope: str,
    target_label: str,
    unit_id: str,
) -> AcquisitionAuthorityEntry:
    """Create a real typed test registry row without inheriting production claims."""
    base = _entry()
    values = {
        name: getattr(base, name)
        for name in AcquisitionAuthorityEntry.model_fields
        if name != "entry_id"
    }
    values.update(
        {
            "source_provenance_class": None,
            "target_variable": target_label,
            "landing_dataset_id": f"acquisition.test.p07.{suffix}",
            "landing_distribution_id": f"acquisition.test.p07.{suffix}.json",
            "source_catalog_dataset_id": f"fixture.p07.{suffix}",
            "source_catalog_distribution_id": f"fixture.p07.{suffix}.metadata",
            "upstream_metric_id": f"metric.{suffix}",
            "catalog_raw_variable": stable_id,
            "raw_field": "value",
            "raw_unit": unit_id,
            "canonical_unit": unit_id,
            "unit_transform": "identity",
            "unit_transform_ref": f"fabric://units/{unit_id}-identity/v1",
            "evidence_refs": (f"fixture://p07/semantic-record/{suffix}",),
            "schema_contract_ref": f"fixture://p07/{namespace}@1.0.0",
            "schema_columns": (
                AuthoritySchemaColumn(name="value", logical_types=("number",), nullable=False),
            ),
            "l5_family_id": "p07_test_owned_semantic_records",
            "title": target_label,
            "description": "Synthetic content-addressed candidate metadata; no observations.",
            "country_codes": ("TST",),
            "temporal_start": "2020",
            "temporal_end": "2024",
            "source_measure_scope": AcquisitionSourceMeasureScope(
                population=population,
                temporal_granularity=time_scope,
                jurisdiction_ref="TST",
                time_period_basis="calendar_year",
                source_geography_id="TST",
                geography_ref="TST",
            ),
            "source_semantic_definition_ref": definition_ref,
            "source_representation_ref": representation_ref,
        }
    )
    return build_authority_entry(**values)


def _allocated_tree_bytes(root: Path) -> tuple[int, int, int | None]:
    """Count fixture files and logical/allocated bytes without reading payloads."""
    file_count = 0
    logical_bytes = 0
    allocated_bytes: int | None = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        stat = path.stat()
        file_count += 1
        logical_bytes += stat.st_size
        if not hasattr(stat, "st_blocks"):
            allocated_bytes = None
        elif allocated_bytes is not None:
            allocated_bytes += stat.st_blocks * 512
    return file_count, logical_bytes, allocated_bytes


def _percentile(values: list[float], percentile: int) -> float:
    ordered = sorted(values)
    rank = max(1, (len(ordered) * percentile + 99) // 100)
    return ordered[min(rank - 1, len(ordered) - 1)]


def _source_entry_key(entry: AcquisitionAuthorityEntry) -> tuple[str, str, str, str | None] | None:
    """Read the typed selected-ref tuple without calling the index key helper."""
    ref = entry.source_semantic_definition_ref
    if ref is None:
        return None
    return _definition_identity(ref)


def _publish_registry_snapshot(path: Path, registry: AcquisitionAuthorityRegistry) -> None:
    """Publish a test-owned registry through Core's existing atomic writer."""
    write_bytes_atomic(path, registry.model_dump_json().encode("utf-8"))


def _run_semantic_corpus_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
    *,
    corpus_records: int,
) -> None:
    """Measure one real-record profile; do not imply §6 100k/300k completion."""
    store = FileSystemCAS(tmp_path / "cas")
    evidence_bytes = b"test-owned synthetic semantic fixture; no empirical or authority claim\n"
    evidence_ref = store.put_bytes(
        evidence_bytes,
        PutOptions(kind="test.p07.semantic_fixture_evidence", media_type="text/plain"),
        return_selected_profile=True,
    )
    record_specs: list[tuple[str, str, str, str, str]] = []
    for index in range(_TRUTH_KEYS):
        if index == 0:
            record_specs.append(
                (
                    "public.health",
                    "annual_visits",
                    "r1",
                    "Annual count of outpatient visits in a test-owned population.",
                    "count",
                )
            )
        elif index == 1:
            record_specs.append(
                (
                    "public.health",
                    "annual_population",
                    "r1",
                    "Annual resident population in a test-owned scope.",
                    "count",
                )
            )
        elif index == 2:
            record_specs.append(
                (
                    "public.health",
                    "visits_per_resident",
                    "r1",
                    "Test-defined ratio of annual visits to resident population.",
                    "ratio",
                )
            )
        elif index == 3:
            record_specs.append(
                (
                    "public.transport",
                    "monthly_fare_revenue",
                    "r1",
                    "Monthly fare revenue for a test-owned transit system.",
                    "flow",
                )
            )
        else:
            domain = _DOMAINS[index % len(_DOMAINS)]
            record_specs.append(
                (
                    domain,
                    f"truth_measure_{index:02d}",
                    "r1",
                    f"Test-owned semantic truth record {index:02d}.",
                    "count" if domain == "public.health" else "flow",
                )
            )

    # Same namespaced local identifier, different declared revision and meaning.
    # These are real distinct CAS records rather than fabricated ArtifactRefs.
    for index in range(_NEAR_MISS_REVISIONS):
        namespace, stable_id, _revision, meaning, _form = record_specs[index]
        record_specs.append(
            (
                namespace,
                stable_id,
                "r2",
                f"Distinct revised meaning for {meaning}; not equivalent to r1.",
                "count" if namespace == "public.health" else "flow",
            )
        )

    while len(record_specs) < corpus_records:
        index = len(record_specs)
        domain = _DOMAINS[index % len(_DOMAINS)]
        if index < _TRUTH_KEYS + _NEAR_MISS_REVISIONS + 4:
            stable_id = "shared_local_label"
        else:
            stable_id = f"measure_{_SEED % 1_000_000}_{index:06d}"
        record_specs.append(
            (
                domain,
                stable_id,
                "r1",
                f"Distinct test-owned definition/revision record {index:06d}.",
                "count" if domain == "public.health" else "flow",
            )
        )

    assert len(record_specs) == corpus_records
    definition_refs: list[VariableSemanticDefinitionRef] = []
    representation_refs: list[VariableRepresentationRef] = []
    expected_specs: list[tuple[str, str, str, str, str]] = []

    generation_started = time.perf_counter()
    for namespace, stable_id, revision, meaning, form in record_specs:
        definition_ref = _put_definition(
            store,
            evidence_ref=evidence_ref,
            namespace=namespace,
            stable_id=stable_id,
            revision=revision,
            meaning=meaning,
        )
        if form == "ratio":
            quantity_kind = "parameter"
            measure_form = "ratio"
            unit_id = "ratio"
            numerator_ref = definition_refs[0]
            denominator_ref = definition_refs[1]
        elif form == "count":
            quantity_kind = "count"
            measure_form = "count"
            unit_id = "count"
            numerator_ref = None
            denominator_ref = None
        else:
            quantity_kind = "flow"
            measure_form = "absolute"
            unit_id = "fixture_currency"
            numerator_ref = None
            denominator_ref = None
        time_support = "period_total"
        temporal_granularity = (
            "monthly"
            if namespace == "public.transport" and stable_id == "monthly_fare_revenue"
            else "annual"
        )
        representation_ref = _put_representation(
            store,
            semantic_ref=definition_ref,
            representation_id=f"{namespace}.{stable_id}.representation",
            revision=revision,
            quantity_kind=quantity_kind,
            measure_form=measure_form,
            unit_id=unit_id,
            time_support=time_support,
            temporal_granularity=temporal_granularity,
            numerator_ref=numerator_ref,
            denominator_ref=denominator_ref,
        )
        definition_refs.append(definition_ref)
        representation_refs.append(representation_ref)
        expected_specs.append((namespace, stable_id, revision, meaning, form))
    generation_seconds = time.perf_counter() - generation_started

    # A distinct selected profile changes producer metadata only. The payload,
    # schema, and declared evidence input stay identical and both views are real.
    profile_variant_ref = _put_definition(
        store,
        evidence_ref=evidence_ref,
        namespace=record_specs[0][0],
        stable_id=record_specs[0][1],
        revision=record_specs[0][2],
        meaning=record_specs[0][3],
        producer=ProducerInfo(component="test.p07.profile-variant", version="2"),
    )
    assert profile_variant_ref.artifact_id == definition_refs[0].artifact_id
    assert profile_variant_ref.manifest_profile_sha256 != definition_refs[0].manifest_profile_sha256
    profile_variant_representation_ref = _put_representation(
        store,
        semantic_ref=profile_variant_ref,
        representation_id="public.health.annual_visits.profile_variant",
        revision="r1",
        quantity_kind="count",
        measure_form="count",
        unit_id="count",
        time_support="period_total",
    )

    # Reopen each unique typed record through a fresh real CAS reader. This is
    # full typed-record validation for the 1k corpus, not empirical evidence.
    reader = FileSystemCAS.open_existing_read_only(tmp_path / "cas")
    read_counts: Counter[str] = Counter()
    payload_bytes_returned = 0
    original_get_bytes = FileSystemCAS.get_bytes
    original_get_manifest = FileSystemCAS.get_manifest

    def counted_get_bytes(self: FileSystemCAS, ref: ArtifactID | ArtifactRef | str) -> bytes:
        nonlocal payload_bytes_returned
        value = original_get_bytes(self, ref)
        if self.root == store.root:
            read_counts["get_bytes"] += 1
            payload_bytes_returned += len(value)
        return value

    def counted_get_manifest(
        self: FileSystemCAS,
        ref: ArtifactID | ArtifactRef | str,
    ) -> ArtifactManifest:
        value = original_get_manifest(self, ref)
        if self.root == store.root:
            read_counts["get_manifest"] += 1
        return value

    monkeypatch.setattr(FileSystemCAS, "get_bytes", counted_get_bytes)
    monkeypatch.setattr(FileSystemCAS, "get_manifest", counted_get_manifest)
    verification_started = time.perf_counter()
    for index, (definition_ref, representation_ref, spec) in enumerate(
        zip(definition_refs, representation_refs, expected_specs, strict=True)
    ):
        loaded_definition = validate_core_model_json_artifact(
            VariableSemanticDefinition,
            reader,
            definition_ref,
        )
        assert (
            loaded_definition.namespace,
            loaded_definition.stable_id,
            loaded_definition.revision,
        ) == (
            spec[0],
            spec[1],
            spec[2],
        )
        loaded_representation = load_variable_representation(reader, representation_ref)
        assert loaded_representation.semantic_definition_ref == definition_ref
        if index == 2:
            assert loaded_representation.numerator_ref == definition_refs[0]
            assert loaded_representation.denominator_ref == definition_refs[1]
            validate_core_model_json_artifact(
                VariableSemanticDefinition,
                reader,
                loaded_representation.numerator_ref,
            )
            validate_core_model_json_artifact(
                VariableSemanticDefinition,
                reader,
                loaded_representation.denominator_ref,
            )
    validate_core_model_json_artifact(VariableSemanticDefinition, reader, profile_variant_ref)
    assert (
        load_variable_representation(
            reader, profile_variant_representation_ref
        ).semantic_definition_ref
        == profile_variant_ref
    )
    verification_seconds = time.perf_counter() - verification_started
    corpus_read_counts = dict(read_counts)
    corpus_payload_bytes_returned = payload_bytes_returned

    entries: list[AcquisitionAuthorityEntry] = []
    for index, (definition_ref, representation_ref, spec) in enumerate(
        zip(definition_refs, representation_refs, expected_specs, strict=True)
    ):
        namespace, stable_id, revision, _meaning, form = spec
        unit_id = {"count": "count", "ratio": "ratio", "flow": "fixture_currency"}[form]
        label = f"{namespace}.{stable_id}"
        if index < _TRUTH_KEYS:
            for alternative in range(_ALTERNATIVES_PER_TRUTH_KEY):
                entries.append(
                    _entry_for_record(
                        definition_ref,
                        representation_ref,
                        namespace=namespace,
                        stable_id=stable_id,
                        suffix=f"truth-{index:02d}-source-{alternative:02d}",
                        population=f"population:test-{alternative:02d}",
                        time_scope="annual" if alternative < 2 else "monthly",
                        target_label=(
                            label if alternative % 2 == 0 else f"label-{alternative:02d}"
                        ),
                        unit_id=unit_id,
                    )
                )
        elif index < _TRUTH_KEYS + _NEAR_MISS_REVISIONS:
            # Same local label and namespace, but a distinct exact revision.
            entries.append(
                _entry_for_record(
                    definition_ref,
                    representation_ref,
                    namespace=namespace,
                    stable_id=stable_id,
                    suffix=f"near-miss-revision-{index:02d}",
                    population="population:test-near-miss",
                    time_scope="annual",
                    target_label=label,
                    unit_id=unit_id,
                )
            )
        else:
            entries.append(
                _entry_for_record(
                    definition_ref,
                    representation_ref,
                    namespace=namespace,
                    stable_id=stable_id,
                    suffix=f"distractor-{index:06d}",
                    population="population:test-distractor",
                    time_scope="annual",
                    target_label=(
                        "shared_local_label" if stable_id == "shared_local_label" else label
                    ),
                    unit_id=unit_id,
                )
            )

    entries.append(
        _entry_for_record(
            profile_variant_ref,
            profile_variant_representation_ref,
            namespace=record_specs[0][0],
            stable_id=record_specs[0][1],
            suffix="truth-00-distinct-selected-profile",
            population="population:test-distinct-profile",
            time_scope="annual",
            target_label="same-content-distinct-selected-profile",
            unit_id="count",
        )
    )

    initial_entry = entries[0]
    authority, _ = _resolver(tmp_path / "catalog-owner", authority_entry=initial_entry)
    initial_registry_build_started = time.perf_counter()
    built_registry = build_authority_registry(
        baseline_content_sha256=authority.provision.baseline_content_sha256,
        l5_measurement_registry_sha256=(authority.provision.l5_measurement_registry_content_sha256),
        entries=tuple(entries),
    )
    initial_registry_build_seconds = time.perf_counter() - initial_registry_build_started
    initial_registry_publish_started = time.perf_counter()
    _publish_registry_snapshot(authority.registry_path, built_registry)
    initial_registry_publish_seconds = time.perf_counter() - initial_registry_publish_started
    initial_registry_load_started = time.perf_counter()
    registry = authority._load_registry()
    initial_registry_load_seconds = time.perf_counter() - initial_registry_load_started
    assert len(definition_refs) == corpus_records
    assert len({_definition_identity(ref) for ref in definition_refs}) == corpus_records
    expected_registry_rows = corpus_records + (_TRUTH_KEYS * (_ALTERNATIVES_PER_TRUTH_KEY - 1)) + 1
    assert len(registry.entries) == expected_registry_rows
    shared_labels = [spec for spec in expected_specs if spec[1] == "shared_local_label"]
    assert len({spec[0] for spec in shared_labels}) == 4
    assert len(entries) == expected_registry_rows

    # The independent oracle scans every typed Catalog row by explicit ref
    # fields; it does not call or reuse the index builder/key function.
    def exhaustive(
        key: tuple[str, str, str, str | None],
        snapshot: AcquisitionAuthorityRegistry = registry,
    ) -> tuple[AcquisitionAuthorityEntry, ...]:
        return tuple(entry for entry in snapshot.entries if _source_entry_key(entry) == key)

    query_refs = tuple(definition_refs[:_TRUTH_KEYS])
    spec_by_ref = {
        _definition_identity(ref): spec
        for ref, spec in zip(definition_refs, expected_specs, strict=True)
    }
    first_key = artifact_ref_identity_key(query_refs[0])
    authority._semantic_definition_index_cache = None
    cold_started = time.perf_counter()
    indexed_first = authority._source_entries_for_semantic_definition(registry, first_key)
    index_build_seconds = time.perf_counter() - cold_started
    index = authority._semantic_definition_index_cache
    assert index is not None and index.is_complete
    assert index.registry_content_sha256 == registry.content_sha256
    exhaustive_buckets: dict[tuple[str, str, str, str | None], list[AcquisitionAuthorityEntry]] = {}
    for entry in registry.entries:
        key = _source_entry_key(entry)
        if key is not None:
            exhaustive_buckets.setdefault(key, []).append(entry)
    expected_buckets = {
        key: tuple(sorted(bucket, key=lambda entry: entry.entry_id))
        for key, bucket in exhaustive_buckets.items()
    }
    assert index.entries_by_definition == expected_buckets
    assert index.eligible_entry_count == sum(len(bucket) for bucket in expected_buckets.values())
    assert index.indexed_entry_count == index.eligible_entry_count
    assert index.indexed_entry_count == len(registry.entries)
    assert indexed_first == exhaustive(_definition_identity(query_refs[0]))
    reversed_registry = build_authority_registry(
        baseline_content_sha256=authority.provision.baseline_content_sha256,
        l5_measurement_registry_sha256=authority.provision.l5_measurement_registry_content_sha256,
        entries=tuple(reversed(registry.entries)),
    )
    reversed_candidates = authority._source_entries_for_semantic_definition(
        reversed_registry,
        first_key,
    )
    assert {entry.entry_id for entry in reversed_candidates} == {
        entry.entry_id for entry in indexed_first
    }

    indexed_lookup_ms: list[float] = []
    exhaustive_lookup_ms: list[float] = []
    for _ in range(_WARMUPS):
        for ref in query_refs:
            key = artifact_ref_identity_key(ref)
            authority._source_entries_for_semantic_definition(registry, key)
            exhaustive(_definition_identity(ref))
    for _ in range(_SAMPLES):
        for ref in query_refs:
            key = artifact_ref_identity_key(ref)
            started = time.perf_counter_ns()
            authority._source_entries_for_semantic_definition(registry, key)
            indexed_lookup_ms.append((time.perf_counter_ns() - started) / 1_000_000)
            started = time.perf_counter_ns()
            exhaustive(_definition_identity(ref))
            exhaustive_lookup_ms.append((time.perf_counter_ns() - started) / 1_000_000)

    # Selected index candidates are the only rows whose evidence references are
    # reopened for this query cohort; the exhaustive oracle remains metadata-only.
    read_counts.clear()
    payload_bytes_returned = 0
    query_started = time.perf_counter()
    for ref in query_refs:
        key = artifact_ref_identity_key(ref)
        indexed = authority._source_entries_for_semantic_definition(registry, key)
        oracle = exhaustive(_definition_identity(ref))
        assert indexed == oracle
        assert len(indexed) == _ALTERNATIVES_PER_TRUTH_KEY
        assert len({entry.source_measure_scope.population for entry in indexed}) == (
            _ALTERNATIVES_PER_TRUTH_KEY
        )
        for entry in indexed:
            assert entry.source_semantic_definition_ref is not None
            assert entry.source_representation_ref is not None
            loaded = validate_core_model_json_artifact(
                VariableSemanticDefinition,
                reader,
                entry.source_semantic_definition_ref,
            )
            representation = load_variable_representation(reader, entry.source_representation_ref)
            assert representation.semantic_definition_ref == entry.source_semantic_definition_ref
            assert (
                loaded.namespace,
                loaded.stable_id,
                loaded.revision,
            ) == spec_by_ref[_definition_identity(ref)][:3]
    query_seconds = time.perf_counter() - query_started
    query_read_counts = dict(read_counts)
    query_payload_bytes_returned = payload_bytes_returned

    # Equal local labels in different namespaces remain distinct exact refs.
    namespace_collision_start = _TRUTH_KEYS + _NEAR_MISS_REVISIONS
    namespace_collision_refs = tuple(
        definition_refs[namespace_collision_start : namespace_collision_start + 4]
    )
    collision_namespaces: set[str] = set()
    for ref in namespace_collision_refs:
        indexed = authority._source_entries_for_semantic_definition(
            registry,
            artifact_ref_identity_key(ref),
        )
        oracle = exhaustive(_definition_identity(ref))
        assert indexed == oracle
        assert len(indexed) == 1
        assert indexed[0].source_semantic_definition_ref == ref
        namespace = spec_by_ref[_definition_identity(ref)][0]
        collision_namespaces.add(namespace)
    assert len(collision_namespaces) == 4
    assert all(
        expected_specs[index][1] == "shared_local_label"
        for index in range(namespace_collision_start, namespace_collision_start + 4)
    )

    # A valid record omitted from the registry is a true query miss. A changed
    # revision reuses no old exact-reference bucket.
    near_miss_ref = definition_refs[_TRUTH_KEYS]
    assert _definition_identity(near_miss_ref) != _definition_identity(query_refs[0])
    near_miss_candidates = authority._source_entries_for_semantic_definition(
        registry,
        artifact_ref_identity_key(near_miss_ref),
    )
    assert near_miss_candidates == exhaustive(_definition_identity(near_miss_ref))
    assert len(near_miss_candidates) == 1
    assert near_miss_candidates[0].target_variable == entries[0].target_variable
    assert expected_specs[_TRUTH_KEYS][3] != expected_specs[0][3]

    unknown_ref = _put_definition(
        store,
        evidence_ref=evidence_ref,
        namespace="public.health",
        stable_id="required_but_unregistered",
        revision="r1",
        meaning="A valid test-owned record intentionally absent from the Catalog registry.",
    )
    assert (
        authority._source_entries_for_semantic_definition(
            registry,
            artifact_ref_identity_key(unknown_ref),
        )
        == ()
    )

    # Same payload bytes with another valid selected manifest profile are a
    # separate exact-ref bucket, represented by their own source row.
    assert profile_variant_ref.artifact_id == query_refs[0].artifact_id
    assert _definition_identity(profile_variant_ref) != _definition_identity(query_refs[0])
    validate_core_model_json_artifact(VariableSemanticDefinition, reader, profile_variant_ref)
    profile_variant_candidates = authority._source_entries_for_semantic_definition(
        registry,
        artifact_ref_identity_key(profile_variant_ref),
    )
    assert len(profile_variant_candidates) == 1
    assert profile_variant_candidates[0].source_semantic_definition_ref == profile_variant_ref

    # Changed registry content makes the update visible; returning to the old
    # snapshot rebuilds its exact bucket rather than leaking the new row.
    updated_source = _entry_for_record(
        query_refs[0],
        representation_refs[0],
        namespace=record_specs[0][0],
        stable_id=record_specs[0][1],
        suffix="truth-00-new-source-after-index-build",
        population="population:test-new-source",
        time_scope="annual",
        target_label="new-label-for-same-exact-definition",
        unit_id="count",
    )
    updated_registry_payload = build_authority_registry(
        baseline_content_sha256=authority.provision.baseline_content_sha256,
        l5_measurement_registry_sha256=authority.provision.l5_measurement_registry_content_sha256,
        entries=(*registry.entries, updated_source),
    )

    old_registry_raw_sha256 = hashlib.sha256(authority.registry_path.read_bytes()).hexdigest()
    update_overlap_barrier = Barrier(2)
    old_registry_bytes_read = Event()
    updated_registry_published = Event()
    reader_thread_ident: int | None = None
    observed_old_registry_raw_sha256: str | None = None
    observed_old_registry_raw_bytes: int | None = None
    reader_gate_wait_seconds: float | None = None
    original_path_read_bytes = Path.read_bytes

    def read_registry_bytes_while_writer_waits(path: Path) -> bytes:
        nonlocal observed_old_registry_raw_bytes
        nonlocal observed_old_registry_raw_sha256
        nonlocal reader_gate_wait_seconds
        raw = original_path_read_bytes(path)
        if path == authority.registry_path and get_ident() == reader_thread_ident:
            observed_old_registry_raw_sha256 = hashlib.sha256(raw).hexdigest()
            observed_old_registry_raw_bytes = len(raw)
            old_registry_bytes_read.set()
            gate_started = time.perf_counter()
            if not updated_registry_published.wait(timeout=30):
                raise TimeoutError("registry writer did not publish while owner read was held")
            reader_gate_wait_seconds = time.perf_counter() - gate_started
        return raw

    def publish_updated_snapshot() -> float:
        update_overlap_barrier.wait(timeout=30)
        if not old_registry_bytes_read.wait(timeout=30):
            raise TimeoutError("owner did not read the old registry before publication")
        publish_started = time.perf_counter()
        _publish_registry_snapshot(authority.registry_path, updated_registry_payload)
        updated_registry_published.set()
        return time.perf_counter() - publish_started

    def load_and_query_old_snapshot() -> tuple[
        str,
        tuple[str, ...],
        tuple[str, ...],
        float,
        float,
        float,
    ]:
        nonlocal reader_thread_ident
        update_overlap_barrier.wait(timeout=30)
        reader_thread_ident = get_ident()
        owner_load_started = time.perf_counter()
        loaded_snapshot = authority._load_registry()
        owner_load_seconds = time.perf_counter() - owner_load_started
        index_query_started = time.perf_counter()
        indexed_rows = authority._source_entries_for_semantic_definition(
            loaded_snapshot,
            first_key,
        )
        index_query_seconds = time.perf_counter() - index_query_started
        oracle_started = time.perf_counter()
        exhaustive_rows = exhaustive(_definition_identity(query_refs[0]), loaded_snapshot)
        oracle_seconds = time.perf_counter() - oracle_started
        return (
            loaded_snapshot.content_sha256,
            tuple(row.entry_id for row in indexed_rows),
            tuple(row.entry_id for row in exhaustive_rows),
            owner_load_seconds,
            index_query_seconds,
            oracle_seconds,
        )

    update_overlap_started = time.perf_counter()
    with monkeypatch.context() as read_patch:
        read_patch.setattr(Path, "read_bytes", read_registry_bytes_while_writer_waits)
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="p07-registry-update") as pool:
            publish_future = pool.submit(publish_updated_snapshot)
            old_during_update_future = pool.submit(load_and_query_old_snapshot)
            update_publish_seconds = publish_future.result(timeout=60)
            old_during_update_result = old_during_update_future.result(timeout=60)
    concurrent_update_overlap_seconds = time.perf_counter() - update_overlap_started
    assert observed_old_registry_raw_sha256 == old_registry_raw_sha256
    assert observed_old_registry_raw_bytes is not None
    assert reader_gate_wait_seconds is not None
    old_owner_load_seconds_excluding_gate = old_during_update_result[3] - reader_gate_wait_seconds
    assert old_owner_load_seconds_excluding_gate >= 0.0
    assert old_during_update_result[0] == registry.content_sha256
    assert old_during_update_result[1] == old_during_update_result[2]
    assert len(old_during_update_result[1]) == _ALTERNATIVES_PER_TRUTH_KEY

    new_snapshot_owner_load_query_started = time.perf_counter()
    update_reload_started = time.perf_counter()
    updated_registry = authority._load_registry()
    update_reload_seconds = time.perf_counter() - update_reload_started
    assert updated_registry.content_sha256 == updated_registry_payload.content_sha256
    update_visibility_started = time.perf_counter()
    updated_bucket = authority._source_entries_for_semantic_definition(
        updated_registry,
        first_key,
    )
    update_visibility_seconds = time.perf_counter() - update_visibility_started
    new_snapshot_owner_load_query_seconds = (
        time.perf_counter() - new_snapshot_owner_load_query_started
    )
    assert len(updated_bucket) == _ALTERNATIVES_PER_TRUTH_KEY + 1
    updated_index = authority._semantic_definition_index_cache
    assert updated_index is not None and updated_index.is_complete
    assert updated_index.registry_content_sha256 == updated_registry.content_sha256
    updated_oracle_buckets: dict[
        tuple[str, str, str, str | None], list[AcquisitionAuthorityEntry]
    ] = {}
    for entry in updated_registry.entries:
        key = _source_entry_key(entry)
        if key is not None:
            updated_oracle_buckets.setdefault(key, []).append(entry)
    expected_updated_buckets = {
        key: tuple(sorted(bucket, key=lambda entry: entry.entry_id))
        for key, bucket in updated_oracle_buckets.items()
    }
    expected_updated_entry_count = sum(len(bucket) for bucket in expected_updated_buckets.values())
    assert updated_index.entries_by_definition == expected_updated_buckets
    assert updated_index.eligible_entry_count == expected_updated_entry_count
    assert updated_index.indexed_entry_count == expected_updated_entry_count
    assert updated_index.indexed_entry_count == len(updated_registry.entries)
    assert updated_bucket == exhaustive(_definition_identity(query_refs[0]), updated_registry)
    assert len(authority._source_entries_for_semantic_definition(registry, first_key)) == (
        _ALTERNATIVES_PER_TRUTH_KEY
    )

    # Removing a source from the live registry must invalidate the newer cache
    # and remove that row from the exact bucket. The old immutable snapshot
    # remains queryable against its own content identity.
    removed_entry = updated_source
    removed_registry_payload = build_authority_registry(
        baseline_content_sha256=authority.provision.baseline_content_sha256,
        l5_measurement_registry_sha256=authority.provision.l5_measurement_registry_content_sha256,
        entries=tuple(
            entry for entry in updated_registry.entries if entry.entry_id != removed_entry.entry_id
        ),
    )
    removal_publish_started = time.perf_counter()
    _publish_registry_snapshot(authority.registry_path, removed_registry_payload)
    removal_publish_seconds = time.perf_counter() - removal_publish_started
    removal_reload_started = time.perf_counter()
    removed_registry = authority._load_registry()
    removal_reload_seconds = time.perf_counter() - removal_reload_started
    removal_visibility_started = time.perf_counter()
    removed_candidates = authority._source_entries_for_semantic_definition(
        removed_registry,
        first_key,
    )
    removal_visibility_seconds = time.perf_counter() - removal_visibility_started
    removal_index = authority._semantic_definition_index_cache
    assert removal_index is not None and removal_index.is_complete
    assert removal_index.registry_content_sha256 == removed_registry.content_sha256
    assert removed_candidates == exhaustive(_definition_identity(query_refs[0]), removed_registry)
    assert removed_entry.entry_id not in {entry.entry_id for entry in removed_candidates}
    assert len(removed_candidates) == _ALTERNATIVES_PER_TRUTH_KEY

    # A stale snapshot is rebuilt; an actually incomplete builder response uses
    # the live exhaustive fallback rather than returning a false empty bucket.
    stale = _AuthoritySemanticDefinitionIndex(
        registry_content_sha256="0" * 64,
        entries_by_definition={},
        indexed_entry_count=0,
        eligible_entry_count=0,
    )
    authority._semantic_definition_index_cache = stale
    stale_candidates = authority._source_entries_for_semantic_definition(registry, first_key)
    assert stale_candidates == exhaustive(_definition_identity(query_refs[0]))
    rebuilt_index = authority._semantic_definition_index_cache
    assert rebuilt_index is not None
    assert rebuilt_index.registry_content_sha256 == registry.content_sha256
    assert rebuilt_index.is_complete
    incomplete = _AuthoritySemanticDefinitionIndex(
        registry_content_sha256=registry.content_sha256,
        entries_by_definition={},
        indexed_entry_count=0,
        eligible_entry_count=len(registry.entries),
    )
    monkeypatch.setattr(
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority._build_authority_semantic_definition_index",
        lambda _: incomplete,
    )
    authority._semantic_definition_index_cache = None
    assert not incomplete.is_complete
    assert authority._source_entries_for_semantic_definition(registry, first_key) == exhaustive(
        _definition_identity(query_refs[0])
    )

    file_count, logical_bytes, allocated_bytes = _allocated_tree_bytes(tmp_path)
    max_scratch_bytes = _MAX_SCRATCH_BYTES if corpus_records == _RECORDS else _OPT_IN_SCRATCH_BYTES
    assert allocated_bytes is None or allocated_bytes <= max_scratch_bytes
    report = {
        "scope": f"genuine_{corpus_records // 1000}k_typed_definition_revision_records_only",
        "full_spec_100k_300k_acceptance": "not_established",
        "seed": _SEED,
        "unique_definition_revision_records": len(definition_refs),
        "unique_exact_selected_definition_refs": len(
            {_definition_identity(ref) for ref in definition_refs}
        ),
        "same_content_distinct_valid_selected_profiles": 1,
        "catalog_registry_rows": len(registry.entries),
        "registry_reopened_from_canonical_test_owner_path": True,
        "truth_keys": len(query_refs),
        "source_alternatives_per_truth_key": _ALTERNATIVES_PER_TRUTH_KEY,
        "same_namespace_revision_near_misses": _NEAR_MISS_REVISIONS,
        "same_local_id_in_distinct_namespaces": 4,
        "nonfiscal_query_domains": sorted(
            {spec_by_ref[_definition_identity(ref)][0] for ref in query_refs}
        ),
        "namespace_collision_exact_queries": len(namespace_collision_refs),
        "namespace_collision_distinct_namespaces": len(collision_namespaces),
        "same_label_different_meaning_records": _NEAR_MISS_REVISIONS,
        "distinct_profile_ref_adversary_is_real_selected_view": True,
        "required_unknown_ref_is_valid_but_unregistered": True,
        "unregistered_unknown_probe_records": 1,
        "declared_ratio_relation_edges": 2,
        "corpus_generation_workers": 1,
        "concurrency_workers": 2,
        "concurrent_index_updates": "atomic_registry_publish_with_held_old_snapshot_query",
        "concurrent_registry_update_overlap": {
            "workers": 2,
            "owner_registry_read_held_across_atomic_publish": True,
            "old_snapshot_content_sha256": old_during_update_result[0],
            "old_snapshot_raw_sha256": observed_old_registry_raw_sha256,
            "old_snapshot_raw_bytes": observed_old_registry_raw_bytes,
            "published_snapshot_content_sha256": updated_registry.content_sha256,
            "old_snapshot_query_matches_independent_scan": (
                old_during_update_result[1] == old_during_update_result[2]
            ),
            "old_snapshot_bucket_rows": len(old_during_update_result[1]),
            "new_snapshot_loaded_after_atomic_publish": (
                updated_registry.content_sha256 == updated_registry_payload.content_sha256
            ),
            "elapsed_seconds": concurrent_update_overlap_seconds,
        },
        "registry_owner_load_and_query_seconds": {
            "held_old_snapshot_load_excluding_controlled_wait": (
                old_owner_load_seconds_excluding_gate
            ),
            "held_old_snapshot_exact_index_query": old_during_update_result[4],
            "held_old_snapshot_exhaustive_oracle": old_during_update_result[5],
            "fresh_new_snapshot_load": update_reload_seconds,
            "fresh_new_snapshot_first_exact_index_query_including_rebuild": (
                update_visibility_seconds
            ),
            "fresh_new_snapshot_owner_load_plus_first_query": (
                new_snapshot_owner_load_query_seconds
            ),
            "boundary": (
                "warm old load includes registry Path.read_bytes/raw hash/cache hit plus baseline "
                "SHA-256 verification; fresh new load includes registry read/hash/parse/schema "
                "validation plus baseline hash; first new exact-index query includes index "
                "rebuild; timings are API-level wall time, not physical device I/O or full consumer "
                "proof"
            ),
        },
        "registry_lifecycle_seconds": {
            "initial_registry_build": initial_registry_build_seconds,
            "initial_registry_atomic_publish": initial_registry_publish_seconds,
            "initial_registry_owner_load": initial_registry_load_seconds,
            "add_exact_source_publish": update_publish_seconds,
            "reload_added_registry": update_reload_seconds,
            "first_query_after_add": update_visibility_seconds,
            "remove_exact_source_publish": removal_publish_seconds,
            "reload_removed_registry": removal_reload_seconds,
            "first_query_after_remove": removal_visibility_seconds,
        },
        "independent_oracle_registry_rows": len(registry.entries),
        "independent_oracle_definition_key_count": len(expected_buckets),
        "updated_registry_rows": len(updated_registry.entries),
        "updated_independent_oracle_definition_key_count": len(expected_updated_buckets),
        "updated_indexed_entry_count": updated_index.indexed_entry_count,
        "updated_index_complete_and_full_map_matches_oracle": (
            updated_index.is_complete
            and updated_index.entries_by_definition == expected_updated_buckets
        ),
        "timed_indexed_vs_exhaustive_query_key_count": len(query_refs),
        "index_build_seconds": index_build_seconds,
        "warmups_per_query_operation": _WARMUPS,
        "samples_per_query_operation": _SAMPLES,
        "indexed_lookup_ms": {
            "p50": statistics.median(indexed_lookup_ms),
            "p95": _percentile(indexed_lookup_ms, 95),
            "p99": _percentile(indexed_lookup_ms, 99),
        },
        "exhaustive_lookup_ms": {
            "p50": statistics.median(exhaustive_lookup_ms),
            "p95": _percentile(exhaustive_lookup_ms, 95),
            "p99": _percentile(exhaustive_lookup_ms, 99),
        },
        "corpus_generation_seconds": generation_seconds,
        "corpus_full_typed_reopen_seconds": verification_seconds,
        "indexed_query_cohort_seconds": query_seconds,
        "corpus_owner_api_reads": corpus_read_counts,
        "corpus_payload_bytes_returned_by_get_bytes": corpus_payload_bytes_returned,
        "query_owner_api_reads": query_read_counts,
        "query_payload_bytes_returned_by_get_bytes": query_payload_bytes_returned,
        "read_measurement_scope": "actual FileSystemCAS get_bytes/get_manifest method calls; not OS/device I/O",
        "index_equivalent_to_independent_full_registry_exact_map": True,
        "update_visible_for_new_registry_snapshot": True,
        "removed_source_disappears_from_new_registry_snapshot": True,
        "stale_snapshot_rebuilt": True,
        "incomplete_index_used_exhaustive_fallback": True,
        "scratch_file_count": file_count,
        "scratch_logical_bytes": logical_bytes,
        "scratch_allocated_bytes": allocated_bytes,
        "scratch_budget_bytes": max_scratch_bytes,
        "proposed_test_runner_budget": {
            "process_tree_wall_seconds": _PROFILE_MAX_WALL_SECONDS,
            "process_tree_peak_rss_bytes": _PROFILE_MAX_PROCESS_TREE_RSS_BYTES,
            "scratch_allocated_bytes": max_scratch_bytes,
            "corpus_generation_workers": 1,
            "registry_update_overlap_workers": 2,
            "scope": "local_test_profile_cap_not_deployment_SLO",
            "wall_and_rss_enforcement": "external_process_budget_supervisor_required",
        },
        "timing_status": "descriptive_local_measurement_no_SLA_claim",
        "semantic_status": "test_owned_typed_records_fixture_evidence_only",
    }
    record_property("p07_semantic_corpus_scale", json.dumps(report, sort_keys=True))
    print("P07_SEMANTIC_CORPUS_SCALE " + json.dumps(report, sort_keys=True))


def test_genuine_semantic_corpus_1k_index_matches_exhaustive_and_rebuilds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    """Keep the ordinary bounded 1k profile available to focused checks."""
    _run_semantic_corpus_profile(
        tmp_path,
        monkeypatch,
        record_property,
        corpus_records=_RECORDS,
    )


@pytest.mark.skipif(
    os.environ.get(_PROFILE_ENV) != "10k",
    reason=f"set {_PROFILE_ENV}=10k to admit the bounded 10k profile explicitly",
)
def test_genuine_semantic_corpus_10k_index_matches_exhaustive_and_rebuilds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    """Measure the intermediate real-record profile with the fixed truth subset."""
    _run_semantic_corpus_profile(
        tmp_path,
        monkeypatch,
        record_property,
        corpus_records=_MEDIUM_PROFILE_RECORDS,
    )


@pytest.mark.skipif(
    os.environ.get(_PROFILE_ENV) != "30k",
    reason=f"set {_PROFILE_ENV}=30k to admit the bounded 30k profile explicitly",
)
def test_genuine_semantic_corpus_30k_index_matches_exhaustive_and_rebuilds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Callable[[str, object], None],
) -> None:
    """Run the separately admitted 30k profile; this does not qualify 300k."""
    _run_semantic_corpus_profile(
        tmp_path,
        monkeypatch,
        record_property,
        corpus_records=_LARGE_PROFILE_RECORDS,
    )
