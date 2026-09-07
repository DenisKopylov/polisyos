"""Exercise canonical case admission from real persisted S2 producer outputs."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core import artifacts, canon
from polisyos.core.security import tenant_scope
from polisyos.pdc import (
    Layer2S2DesignSearchInput,
    PersistedS2DesignSearchRun,
    persist_s2_design_search_run,
    run_s2_shadow_design_loop,
)
from polisyos.runtime.quality.global_case_index import (
    GlobalCaseIndexError,
    GlobalCaseIndexProducer,
    GlobalCaseIndexSnapshot,
)

_TENANT = "tenant:case-index"
_CELL = "cell:case-index"
_FAMILIES = ("credit_guarantee", "interest_rate_buydown", "cash_grant")


def _persist_case(
    store: artifacts.FileSystemCAS,
    *,
    case_id: str = "case:producer-one",
    run_id: str = "run:producer-one",
    tenant_id: str = _TENANT,
    cell_id: str | None = _CELL,
    families: tuple[str, ...] = _FAMILIES,
) -> PersistedS2DesignSearchRun:
    search_input = Layer2S2DesignSearchInput(
        case_id=case_id,
        intent_ref=f"intent:{case_id}",
        grammar_ref="grammar:case-index-test",
        instrument_families=families,
        parameter_space={"coverage": ("partial_portfolio",)},
        actor_ref="actor:case-index-test",
        domain="credit",
        objective_refs=("objective:credit-access",),
        construct_refs=("construct:credit-access",),
        authority_profile_ref="authority_profile.shadow",
        generated_at=datetime(2026, 9, 7, tzinfo=UTC),
    )
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        return persist_s2_design_search_run(
            run_s2_shadow_design_loop(search_input),
            store=store,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )


def _put_changed_binding(
    store: artifacts.FileSystemCAS,
    persisted: PersistedS2DesignSearchRun,
    *,
    changed: dict[str, object] | None = None,
    producer: artifacts.ProducerInfo | None = None,
    schema_version: str | None = None,
) -> artifacts.ArtifactRef:
    payload = persisted.binding.model_dump(mode="json")
    payload.update({"binding_id": "binding:adversarial", **(changed or {})})
    source = store.get_manifest(persisted.binding_ref.artifact_id)
    assert source.artifact_schema is not None
    return store.put_json(
        payload,
        artifacts.PutOptions(
            kind=source.kind,
            media_type=source.media_type,
            schema=artifacts.SchemaInfo(
                name=source.artifact_schema.name,
                version=schema_version or source.artifact_schema.version,
            ),
            producer=producer or source.producer,
        ),
    )


def test_real_s2_producer_emits_persisted_content_bound_case_index(tmp_path: Path) -> None:
    """Resolve real linked owner artifacts and preserve their vocabulary values."""
    store = artifacts.FileSystemCAS(tmp_path / "cas", ownership_enforced=True)
    persisted = _persist_case(store)
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL):
        visible_ids = store.for_tenant(_TENANT, _CELL).iter_artifact_ids()
        snapshot_ref, snapshot = GlobalCaseIndexProducer(store).produce()
        reloaded = GlobalCaseIndexSnapshot.model_validate_json(
            store.get_bytes(snapshot_ref.artifact_id)
        )
        assert store.verify(snapshot_ref.artifact_id).ok
        assert canon.content_hash(store.get_bytes(snapshot_ref.artifact_id), prefix=True) == str(
            snapshot_ref.artifact_id
        )
        record = canon.from_canonical_bytes(
            store.get_bytes(persisted.design_record_ref.artifact_id)
        )
    assert reloaded == snapshot
    assert snapshot.scanned_artifact_count == len(visible_ids)
    assert snapshot.source_artifact_refs == (str(persisted.binding_ref.artifact_id),)
    assert snapshot.authority_owner_ref is None
    assert {"s2_bindings_only", "terminality_not_established"} <= set(snapshot.limitation_codes)
    assert snapshot.observed_at.tzinfo is not None
    assert len(snapshot.entries) == 1
    entry = snapshot.entries[0]
    assert (entry.case_id, entry.run_id, entry.tenant_id, entry.cell_id) == (
        "case:producer-one", "run:producer-one", _TENANT, _CELL
    )
    assert entry.binding_ref == str(persisted.binding_ref.artifact_id)
    assert entry.design_record_ref == str(persisted.design_record_ref.artifact_id)
    assert entry.search_ledger_ref == str(persisted.search_ledger_ref.artifact_id)
    assert set(entry.instrument_families) == set(_FAMILIES)
    assert entry.candidate_ref == record["candidate_ref"]


def test_case_field_names_do_not_identify_the_canonical_vocabulary(tmp_path: Path) -> None:
    """A different artifact carrying all familiar field names remains unrelated."""
    store = artifacts.FileSystemCAS(tmp_path / "cas", ownership_enforced=True)
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL):
        decoy = store.put_json(
            {
                "case_id": "case:not-a-design-case",
                "resource_kind": "case",
                "instrument_family_coverage": ["credit_guarantee"],
                "schema_version": "policyos.pdc.run_bound_design_record_binding.v1",
            },
            artifacts.PutOptions(kind="forecasting.loop_counter", media_type="application/json"),
        )
        _, snapshot = GlobalCaseIndexProducer(store).produce()
    assert snapshot.entries == ()
    assert snapshot.source_artifact_refs == ()
    assert snapshot.scanned_artifact_count == 1
    assert str(decoy.artifact_id) not in snapshot.source_artifact_refs


@pytest.mark.parametrize(
    "changed",
    [
        {"case_id": "case:forged-with-unchanged-ledger"},
        {"search_ledger_id": "ledger:forged-with-unchanged-content"},
        {"design_record_record_id": "record:forged-with-unchanged-content"},
    ],
)
def test_linked_content_identity_must_match_binding(
    tmp_path: Path, changed: dict[str, object]
) -> None:
    """Shape-valid declarations cannot replace independently resolved owner bytes."""
    store = artifacts.FileSystemCAS(tmp_path / "cas", ownership_enforced=True)
    persisted = _persist_case(store)
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL):
        _put_changed_binding(store, persisted, changed=changed)
        with pytest.raises(GlobalCaseIndexError):
            GlobalCaseIndexProducer(store).produce()


@pytest.mark.parametrize("field", ["tenant_id", "cell_id"])
def test_native_owned_artifact_cannot_assert_a_different_binding_scope(
    tmp_path: Path, field: str
) -> None:
    """Native CAS admission and typed binding scope must agree."""
    store = artifacts.FileSystemCAS(tmp_path / "cas", ownership_enforced=True)
    persisted = _persist_case(store)
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL):
        _put_changed_binding(store, persisted, changed={field: "foreign-owner"})
        with pytest.raises(GlobalCaseIndexError):
            GlobalCaseIndexProducer(store).produce()


@pytest.mark.parametrize("mismatch", ["producer", "schema"])
def test_canonical_kind_with_unverified_provenance_refuses_the_inventory(
    tmp_path: Path, mismatch: str
) -> None:
    """Malformed canonical members cannot be silently omitted from completeness."""
    store = artifacts.FileSystemCAS(tmp_path / "cas", ownership_enforced=True)
    persisted = _persist_case(store)
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL):
        _put_changed_binding(
            store,
            persisted,
            producer=(
                artifacts.ProducerInfo(component="forged.producer", version="v1")
                if mismatch == "producer" else None
            ),
            schema_version="forged.schema.v1" if mismatch == "schema" else None,
        )
        with pytest.raises(GlobalCaseIndexError):
            GlobalCaseIndexProducer(store).produce()


@pytest.mark.parametrize("families", [[], [" "]])
def test_missing_family_vocabulary_cannot_be_replaced_with_case_identity(
    tmp_path: Path, families: list[str]
) -> None:
    """Coherently rebound ledger bytes still need actual family vocabulary."""
    store = artifacts.FileSystemCAS(tmp_path / "cas", ownership_enforced=True)
    persisted = _persist_case(store)
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL):
        ledger = canon.from_canonical_bytes(
            store.get_bytes(persisted.search_ledger_ref.artifact_id)
        )
        ledger["instrument_family_coverage"] = families
        source = store.get_manifest(persisted.search_ledger_ref.artifact_id)
        changed_ref = store.put_json(
            ledger,
            artifacts.PutOptions(
                kind=source.kind,
                media_type=source.media_type,
                schema=source.artifact_schema,
                producer=source.producer,
            ),
            canon_spec=canon.CanonSpec(forbid_floats=False),
        )
        _put_changed_binding(
            store,
            persisted,
            changed={
                "search_ledger_ref": changed_ref.model_dump(mode="json"),
                "search_ledger_content_digest": str(changed_ref.artifact_id),
            },
        )
        with pytest.raises(GlobalCaseIndexError):
            GlobalCaseIndexProducer(store).produce()


def test_mutated_linked_bytes_refuse_even_after_a_successful_read(tmp_path: Path) -> None:
    """A previously indexed record is resolved again, not trusted from a cache."""
    store = artifacts.FileSystemCAS(tmp_path / "cas", ownership_enforced=True)
    persisted = _persist_case(store)
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL):
        producer = GlobalCaseIndexProducer(store)
        producer.produce()
        blob, _ = store.get_paths(persisted.search_ledger_ref.artifact_id)
        payload = canon.from_canonical_bytes(blob.read_bytes())
        payload["case_id"] = "case:tampered"
        blob.write_bytes(canon.to_canonical_bytes(payload, canon.CanonSpec(forbid_floats=False)))
        with pytest.raises(GlobalCaseIndexError):
            producer.produce()


def test_new_bindings_join_the_next_complete_snapshot(tmp_path: Path) -> None:
    """The same producer sees new cases without indexing its own prior snapshots."""
    store = artifacts.FileSystemCAS(tmp_path / "cas", ownership_enforced=True)
    first = _persist_case(store)
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL):
        producer = GlobalCaseIndexProducer(store)
        first_snapshot_ref, before = producer.produce()
        second = _persist_case(store, case_id="case:second", run_id="run:second")
        _, after = producer.produce()
    assert len(before.entries) == 1
    assert {entry.case_id for entry in after.entries} == {"case:producer-one", "case:second"}
    assert set(after.source_artifact_refs) == {
        str(first.binding_ref.artifact_id), str(second.binding_ref.artifact_id)
    }
    assert str(first_snapshot_ref.artifact_id) not in after.source_artifact_refs


def test_tenant_and_cell_views_never_reuse_another_scopes_cases(tmp_path: Path) -> None:
    """Native ownership restricts enumeration before any case is emitted."""
    store = artifacts.FileSystemCAS(tmp_path / "cas", ownership_enforced=True)
    own = _persist_case(store)
    other_cell = _persist_case(
        store, case_id="case:other-cell", run_id="run:other-cell", cell_id="cell:other"
    )
    other_tenant = _persist_case(
        store, case_id="case:other-tenant", run_id="run:other-tenant", tenant_id="tenant:other"
    )
    producer = GlobalCaseIndexProducer(store)
    for tenant_id, cell_id, persisted in (
        (_TENANT, _CELL, own),
        (_TENANT, "cell:other", other_cell),
        ("tenant:other", _CELL, other_tenant),
    ):
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            _, snapshot = producer.produce()
        assert snapshot.source_artifact_refs == (str(persisted.binding_ref.artifact_id),)
        assert [entry.case_id for entry in snapshot.entries] == [persisted.binding.case_id]


def test_missing_scope_cannot_emit_an_unscoped_inventory(tmp_path: Path) -> None:
    """Missing ambient tenant context cannot become an all-tenant scan."""
    with pytest.raises(GlobalCaseIndexError):
        GlobalCaseIndexProducer(artifacts.FileSystemCAS(tmp_path / "cas", ownership_enforced=True)).produce()
