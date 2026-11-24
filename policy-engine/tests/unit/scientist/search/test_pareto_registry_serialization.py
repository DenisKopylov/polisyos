"""Persistence regressions for the Pareto registry's typed snapshot contract."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

import pytest
from pydantic import BaseModel

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.security import AccessScope, reset_current_access_scope, set_current_access_scope
from polisyos.scientist.methods.search.frontier import policy_candidate_hash
from polisyos.scientist.methods.search.pareto_registry import (
    ParetoRegistry,
    ParetoRegistrySnapshot,
    ParetoView,
)
from polisyos.scientist.methods.search.transfer_context import (
    TransferContext,
    TransferScopeRefusalReason,
    TransferScopeRefusedError,
    TransferTenantScopeStatus,
    anonymize_tenant_id,
)

from .test_objective_availability import _runtime_vector


def _write_diagnostic_candidate(
    registry: ParetoRegistry,
    context: TransferContext,
    candidate_id: str,
    value: float,
) -> str:
    subject = {"candidate_id": candidate_id}
    canonical = json.dumps(subject, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    candidate_hash = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    vector, source = _runtime_vector(values={"policy_value": value})
    assert vector.frontier_objectives("global_feasible", source) == {"policy_value": value}
    evaluation = vector.model_copy(
        update={
            "candidate_id": candidate_id,
            "metadata": {**vector.metadata, "candidate_hash": candidate_hash},
        }
    )
    registry.update(
        context.run_id,
        candidate_hash=candidate_hash,
        evaluation=evaluation,
        seed_payload=subject,
        transfer_context=context,
    )
    return candidate_hash


@contextmanager
def _authenticated_tenant(tenant_id: str) -> Iterator[None]:
    token = set_current_access_scope(
        AccessScope.for_service(tenant_id=tenant_id, cell_id=None, spiffe_id="spiffe://test/search")
    )
    try:
        yield
    finally:
        reset_current_access_scope(token)


def _assert_required_nullable_fields_are_serialized(
    model: BaseModel,
    payload: object,
    *,
    path: str = "snapshot",
) -> None:
    """Require every explicit null on a required model field to survive JSON writing."""
    assert isinstance(payload, dict), path
    for field_name, field in type(model).model_fields.items():
        value = getattr(model, field_name)
        field_path = f"{path}.{field_name}"
        if value is None:
            if field.is_required():
                assert field_name in payload, f"required nullable field omitted: {field_path}"
                assert payload[field_name] is None, f"null changed at {field_path}"
            continue
        if not field.is_required() and field.exclude_if is not None and field.exclude_if(value):
            assert field_name not in payload, f"{field_path}: expected omission by field contract"
            continue
        serialized = payload.get(field_name)
        if isinstance(value, BaseModel):
            _assert_required_nullable_fields_are_serialized(
                value,
                serialized,
                path=field_path,
            )
        elif isinstance(value, Mapping):
            assert isinstance(serialized, dict), field_path
            for key, item in value.items():
                if isinstance(item, BaseModel):
                    _assert_required_nullable_fields_are_serialized(
                        item,
                        serialized.get(key),
                        path=f"{field_path}[{key!r}]",
                    )
        elif isinstance(value, (list, tuple)):
            assert isinstance(serialized, list), field_path
            for index, item in enumerate(value):
                if isinstance(item, BaseModel):
                    _assert_required_nullable_fields_are_serialized(
                        item,
                        serialized[index],
                        path=f"{field_path}[{index}]",
                    )


def test_registry_recomputes_distinct_tied_entries_with_a_shared_ref(tmp_path: Path) -> None:
    """The diagnostic front uses entry identity even when evaluation refs tie."""
    root = tmp_path / "pareto"
    context = TransferContext(task_family="policy", domain="fiscal", run_id="source-run")
    writer = ParetoRegistry(root=root)
    shared_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="test",
        media_type="application/json",
    )
    expected = []
    for candidate_id in ("candidate-a", "candidate-b"):
        subject = {"candidate_id": candidate_id}
        candidate_hash = policy_candidate_hash(subject)
        expected.append(candidate_hash)
        vector, source = _runtime_vector(values={"policy_value": 2.0})
        assert vector.frontier_objectives("global_feasible", source) == {"policy_value": 2.0}
        vector = vector.model_copy(
            update={
                "candidate_id": candidate_id,
                "metadata": {**vector.metadata, "candidate_hash": candidate_hash},
            },
        )
        writer.update(
            "source-run",
            candidate_hash=candidate_hash,
            evaluation=vector,
            candidate_ref=shared_ref,
            seed_payload=subject,
            transfer_context=context,
        )

    reopened = ParetoRegistry(root=root).get_snapshot("source-run", transfer_context=context)
    assert reopened.frontiers["global_feasible"] == sorted(expected)
    assert len(reopened.entries) == 2
    assert all(entry.candidate_ref == shared_ref for entry in reopened.entries.values())
    assert reopened.project_view(ParetoView.GLOBAL_FEASIBLE).ranked_frontier_hashes == ()


def test_registry_round_trips_required_nullable_scope_for_local_and_catalog(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pareto"
    context = TransferContext(task_family="policy", domain="fiscal", run_id="source-run")
    writer = ParetoRegistry(root=root)
    first_hash = _write_diagnostic_candidate(writer, context, "candidate-a", 1.0)

    local_path = writer._snapshot_path("source-run")
    local_payload = json.loads(local_path.read_text(encoding="utf-8"))
    assert "tenant_hash" in local_payload["source_scope"]
    assert local_payload["source_scope"]["tenant_hash"] is None

    fresh_writer = ParetoRegistry(root=root)
    first_read = fresh_writer.get_snapshot("source-run", transfer_context=context)
    _assert_required_nullable_fields_are_serialized(first_read, local_payload)
    second_hash = _write_diagnostic_candidate(fresh_writer, context, "candidate-b", 2.0)

    reloaded = ParetoRegistry(root=root).get_snapshot("source-run", transfer_context=context)
    assert set(reloaded.entries) == {first_hash, second_hash}

    catalog_path = writer._catalog_path(context)
    catalog_payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert "tenant_hash" in catalog_payload["source_scope"]
    assert catalog_payload["source_scope"]["tenant_hash"] is None
    catalog_snapshot = ParetoRegistry._load_snapshot(catalog_path)
    _assert_required_nullable_fields_are_serialized(catalog_snapshot, catalog_payload)

    target = TransferContext(task_family="policy", domain="fiscal", run_id="target-run")
    seed_bundle = ParetoRegistry(root=root).get_seed_bundle(target)
    assert [entry.candidate_hash for entry in seed_bundle.entries] == [second_hash]
    assert seed_bundle.entries[0].seed_only
    assert all(
        refusal.reason is not TransferScopeRefusalReason.INVALID_SOURCE_BODY
        for refusal in seed_bundle.scope_refusals
    )


def test_registry_round_trips_present_tenant_hash(tmp_path: Path) -> None:
    root = tmp_path / "pareto"
    context = TransferContext(task_family="policy", domain="fiscal", run_id="tenant-run")
    registry = ParetoRegistry(root=root)
    with _authenticated_tenant("tenant-alpha"):
        candidate_hash = _write_diagnostic_candidate(registry, context, "tenant-candidate", 1.0)
        loaded = ParetoRegistry(root=root).get_snapshot("tenant-run", transfer_context=context)

    assert set(loaded.entries) == {candidate_hash}
    assert loaded.source_scope is not None
    assert loaded.source_scope.tenant_hash == anonymize_tenant_id("tenant-alpha")
    assert loaded.source_scope.tenant_scope_status is TransferTenantScopeStatus.AUTHENTICATED

    payload = json.loads(registry._snapshot_path("tenant-run").read_text(encoding="utf-8"))
    assert payload["source_scope"]["tenant_hash"] == loaded.source_scope.tenant_hash


def test_registry_reader_refuses_missing_nullable_scope_and_wrong_scope(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pareto"
    context = TransferContext(task_family="policy", domain="fiscal", run_id="source-run")
    registry = ParetoRegistry(root=root)
    candidate_hash = _write_diagnostic_candidate(registry, context, "candidate-d", 1.0)
    path = registry._snapshot_path("source-run")
    original_bytes = path.read_bytes()
    malformed = json.loads(original_bytes)
    del malformed["source_scope"]["tenant_hash"]
    path.write_text(json.dumps(malformed), encoding="utf-8")

    with pytest.raises(TransferScopeRefusedError) as missing_field:
        ParetoRegistry(root=root).get_snapshot("source-run", transfer_context=context)
    assert missing_field.value.refusals[0].reason is TransferScopeRefusalReason.INVALID_SOURCE_BODY

    path.write_bytes(original_bytes)
    restored = ParetoRegistry(root=root).get_snapshot("source-run", transfer_context=context)
    assert set(restored.entries) == {candidate_hash}

    with (
        _authenticated_tenant("tenant-beta"),
        pytest.raises(TransferScopeRefusedError) as scope_mismatch,
    ):
        ParetoRegistry(root=root).get_snapshot("source-run", transfer_context=context)
    assert (
        scope_mismatch.value.refusals[0].reason
        is TransferScopeRefusalReason.CROSS_TENANT_NOT_AUTHORIZED
    )


def test_catalog_reader_returns_invalid_body_refusal_for_missing_required_nullable_field(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pareto"
    source = TransferContext(task_family="policy", domain="fiscal", run_id="source-run")
    registry = ParetoRegistry(root=root)
    candidate_hash = _write_diagnostic_candidate(registry, source, "candidate-e", 1.0)
    target = TransferContext(task_family="policy", domain="fiscal", run_id="target-run")
    original = ParetoRegistry(root=root).get_seed_bundle(target)
    assert [entry.candidate_hash for entry in original.entries] == [candidate_hash]
    assert original.entries[0].seed_only
    assert not original.scope_refusals

    catalog_path = registry._catalog_path(source)
    malformed = json.loads(catalog_path.read_text(encoding="utf-8"))
    del malformed["source_scope"]["tenant_hash"]
    catalog_path.write_text(json.dumps(malformed), encoding="utf-8")

    bundle = ParetoRegistry(root=root).get_seed_bundle(target)

    assert not bundle.entries
    assert [refusal.reason for refusal in bundle.scope_refusals] == [
        TransferScopeRefusalReason.INVALID_SOURCE_BODY
    ]


def test_legacy_v1_snapshot_bytes_keep_the_historical_projection(tmp_path: Path) -> None:
    snapshot = ParetoRegistrySnapshot(schema_version="1.0", loop_id="legacy-run")
    path = tmp_path / "legacy.json"

    ParetoRegistry._write_json(path, snapshot)

    expected = json.dumps(
        snapshot.historical_v1_payload(),
        indent=2,
        ensure_ascii=False,
    ).encode("utf-8")
    assert path.read_bytes() == expected
    assert "source_scope" not in json.loads(path.read_text(encoding="utf-8"))
