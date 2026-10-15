"""Persistence regressions for the Pareto registry's typed snapshot contract."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import BaseModel

from polisyos.scientist.methods.search.pareto_registry import (
    ParetoRegistry,
    ParetoRegistrySnapshot,
)
from polisyos.scientist.methods.search.transfer_context import (
    TransferContext,
    TransferScopeRefusalReason,
    TransferScopeRefusedError,
)
from polisyos.scientist.policy_design.objectives import (
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    PolicyEvaluationVector,
)


def _evaluation(candidate_id: str, value: float) -> PolicyEvaluationVector:
    return PolicyEvaluationVector(
        candidate_id=candidate_id,
        primary={
            "policy_value": ObjectiveChannelValue(
                name="policy_value",
                kind=ObjectiveKind.PRIMARY,
                value=value,
                direction=ObjectiveDirection.MAXIMIZE,
                source="pareto-registry-serialization-test",
            )
        },
    )


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


def test_registry_round_trips_required_nullable_scope_for_local_and_catalog(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pareto"
    context = TransferContext(task_family="policy", domain="fiscal", run_id="source-run")
    writer = ParetoRegistry(root=root)
    writer.update(
        "source-run",
        candidate_hash="sha256:" + "a" * 64,
        evaluation=_evaluation("candidate-a", 1.0),
        seed_payload={"candidate_id": "candidate-a"},
        transfer_context=context,
    )

    local_path = writer._snapshot_path("source-run")
    local_payload = json.loads(local_path.read_text(encoding="utf-8"))
    assert "tenant_hash" in local_payload["source_scope"]
    assert local_payload["source_scope"]["tenant_hash"] is None

    fresh_writer = ParetoRegistry(root=root)
    first_read = fresh_writer.get_snapshot("source-run", transfer_context=context)
    _assert_required_nullable_fields_are_serialized(first_read, local_payload)
    fresh_writer.update(
        "source-run",
        candidate_hash="sha256:" + "b" * 64,
        evaluation=_evaluation("candidate-b", 2.0),
        seed_payload={"candidate_id": "candidate-b"},
        transfer_context=context,
    )

    reloaded = ParetoRegistry(root=root).get_snapshot("source-run", transfer_context=context)
    assert set(reloaded.entries) == {"sha256:" + "a" * 64, "sha256:" + "b" * 64}

    catalog_path = writer._catalog_path(context)
    catalog_payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert "tenant_hash" in catalog_payload["source_scope"]
    assert catalog_payload["source_scope"]["tenant_hash"] is None
    catalog_snapshot = ParetoRegistry._load_snapshot(catalog_path)
    _assert_required_nullable_fields_are_serialized(catalog_snapshot, catalog_payload)

    target = TransferContext(task_family="policy", domain="fiscal", run_id="target-run")
    seed_bundle = ParetoRegistry(root=root).get_seed_bundle(target)
    assert seed_bundle.entries
    assert all(
        refusal.reason is not TransferScopeRefusalReason.INVALID_SOURCE_BODY
        for refusal in seed_bundle.scope_refusals
    )


def test_registry_round_trips_present_tenant_hash(tmp_path: Path) -> None:
    context = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="tenant-run",
        tenant_hash="tenant-alpha",
    )
    registry = ParetoRegistry(root=tmp_path / "pareto")
    registry.update(
        "tenant-run",
        candidate_hash="sha256:" + "c" * 64,
        evaluation=_evaluation("tenant-candidate", 1.0),
        transfer_context=context,
    )

    loaded = ParetoRegistry(root=tmp_path / "pareto").get_snapshot(
        "tenant-run",
        transfer_context=context,
    )
    assert loaded.source_scope is not None
    assert loaded.source_scope.tenant_hash == "tenant-alpha"


def test_registry_reader_refuses_missing_nullable_scope_and_wrong_scope(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pareto"
    context = TransferContext(task_family="policy", domain="fiscal", run_id="source-run")
    registry = ParetoRegistry(root=root)
    registry.update(
        "source-run",
        candidate_hash="sha256:" + "d" * 64,
        evaluation=_evaluation("candidate-d", 1.0),
        transfer_context=context,
    )
    path = registry._snapshot_path("source-run")
    original_bytes = path.read_bytes()
    malformed = json.loads(original_bytes)
    del malformed["source_scope"]["tenant_hash"]
    path.write_text(json.dumps(malformed), encoding="utf-8")

    with pytest.raises(TransferScopeRefusedError) as missing_field:
        ParetoRegistry(root=root).get_snapshot("source-run", transfer_context=context)
    assert missing_field.value.refusals[0].reason is TransferScopeRefusalReason.INVALID_SOURCE_BODY

    path.write_bytes(original_bytes)
    wrong_scope = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="source-run",
        tenant_hash="tenant-beta",
    )
    with pytest.raises(TransferScopeRefusedError) as scope_mismatch:
        ParetoRegistry(root=root).get_snapshot("source-run", transfer_context=wrong_scope)
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
    registry.update(
        "source-run",
        candidate_hash="sha256:" + "e" * 64,
        evaluation=_evaluation("candidate-e", 1.0),
        seed_payload={"candidate_id": "candidate-e"},
        transfer_context=source,
    )
    catalog_path = registry._catalog_path(source)
    malformed = json.loads(catalog_path.read_text(encoding="utf-8"))
    del malformed["source_scope"]["tenant_hash"]
    catalog_path.write_text(json.dumps(malformed), encoding="utf-8")

    target = TransferContext(task_family="policy", domain="fiscal", run_id="target-run")
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
