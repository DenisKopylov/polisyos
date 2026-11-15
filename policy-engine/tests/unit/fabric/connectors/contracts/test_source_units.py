"""Metric-scoped unit declarations preserve actual source and schema identities."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from polisyos.core import artifacts
from polisyos.core.canon import CanonSpec, content_hash, to_canonical_bytes
from polisyos.fabric.connectors.contracts import (
    SOURCE_CONTRACT_FIELD_SET_HASH_PROFILE,
    SchemaType,
    SourceContract,
    SourceContractSemantics,
    SourceMetricDefinition,
    SourceMetricUnitDeclaration,
    build_contract_registry,
    create_source_metric_unit_declaration,
    load_source_metric_unit_declaration,
)
from polisyos.fabric.connectors.sources._contracts import WDI_GENERIC_CONTRACT


def _source(contract=WDI_GENERIC_CONTRACT) -> SourceContract:
    source = SourceContract.from_connector_schema_contract(contract, profile_id="worldbank_wdi")
    return source.model_copy(
        update={
            "semantics": SourceContractSemantics(
                domain=source.semantics.domain,
                metric_definitions=(
                    SourceMetricDefinition(
                        metric_id="TEST.A", unit="count", canonical_field="value"
                    ),
                    SourceMetricDefinition(metric_id="TEST.B", unit="usd", canonical_field="value"),
                ),
            )
        }
    )


def _create(
    store: artifacts.CoreJSONArtifactStore,
    *,
    metric: str = "TEST.A",
    contract=WDI_GENERIC_CONTRACT,
    source=None,
):
    return create_source_metric_unit_declaration(
        store,
        source_contract=_source(contract) if source is None else source,
        contract_registry=build_contract_registry((contract,)),
        connector_contract_id=contract.contract_id,
        connector_contract_version=str(contract.schema_version),
        catalog_dataset_id="source-test",
        catalog_distribution_id="source-test-json",
        catalog_metric_id="test.a" if metric == "TEST.A" else "test.b",
        request_dataset_id=metric,
        source_metric_id=metric,
        raw_field="value",
        normalized_field="value",
        metric_selector_field="indicator_id",
        reported_unit_field="unit",
    )


def _raw_selected(store, payload, *, version=None):
    return store.put_json(
        payload,
        artifacts.PutOptions(
            kind=SourceMetricUnitDeclaration.ARTIFACT_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=SourceMetricUnitDeclaration.ARTIFACT_SCHEMA_NAME,
                version=version or SourceMetricUnitDeclaration.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def test_two_indicators_share_an_unannotated_value_field_without_unit_graft(tmp_path: Path) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    count_ref, usd_ref = _create(store), _create(store, metric="TEST.B")
    count = load_source_metric_unit_declaration(store, count_ref)
    usd = load_source_metric_unit_declaration(store, usd_ref)

    assert WDI_GENERIC_CONTRACT.schema.get_field("value").unit is None
    assert count.normalized_field == usd.normalized_field == "value"
    assert count.declared_unit.unit_id == "count"
    assert usd.declared_unit.unit_id == "usd"
    assert count_ref != usd_ref
    assert count.schema_content_hash == WDI_GENERIC_CONTRACT.schema.content_hash
    # The actual schema retains its key, grain, time, geography and nullability;
    # SourceContract's reduced reconstruction cannot stand in for that owner.
    assert count.schema_content_hash != _source().schema_contract.to_data_schema().content_hash
    assert count.connector_contract.schema.primary_key == ("country_code", "indicator_id", "year")
    assert count.semantic_authority == count.acquisition_permission == "not_established"
    count.validate_raw_metric_rows([{"indicator": {"id": "TEST.A"}, "value": 7}])
    assert count.reported_units([{"indicator_id": "TEST.A", "value": 7, "unit": "count"}]) == (
        "count",
    )
    with pytest.raises(ValueError, match="source_unit_raw_metric_mismatch"):
        count.validate_raw_metric_rows([{"indicator": {"id": "TEST.B"}, "value": 7}])
    with pytest.raises(ValueError, match="source_unit_raw_metric_missing"):
        count.validate_raw_metric_rows([{"value": 7}])
    with pytest.raises(ValueError, match="source_unit_row_metric_mismatch"):
        count.reported_units([{"indicator_id": "TEST.B", "value": 7, "unit": "count"}])


@pytest.mark.parametrize(
    "field",
    ["source_contract_content_hash", "connector_contract_content_hash", "schema_content_hash"],
)
def test_selected_bytes_with_a_wrong_owner_hash_refuse(tmp_path: Path, field: str) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    payload = load_source_metric_unit_declaration(store, _create(store)).model_dump(mode="json")
    payload[field] = "sha256:" + "0" * 64
    with pytest.raises(ValueError):
        load_source_metric_unit_declaration(store, _raw_selected(store, payload))


def test_metric_field_and_request_identity_are_not_aliases(tmp_path: Path) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    selected = load_source_metric_unit_declaration(store, _create(store))
    for replacement in (
        {"request_dataset_id": "TEST.B"},
        {"normalized_field": "indicator_name"},
        {"raw_field": "another_value"},
    ):
        with pytest.raises(ValueError):
            SourceMetricUnitDeclaration.model_validate(
                {**selected.model_dump(mode="python"), **replacement}
            )
    with pytest.raises(ValueError):
        load_source_metric_unit_declaration(
            store, _create(store).model_copy(update={"manifest_profile_sha256": None})
        )


def test_persisted_full_schema_reopens_with_stable_bytes_across_hash_seeds(tmp_path: Path) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    fields = tuple(
        field.model_copy(update={"tags": frozenset({"alpha", "beta", "gamma", "delta"})})
        if field.name == "value"
        else field.model_copy(update={"allowed_values": frozenset({"TEST.A", "TEST.B", "TEST.C"})})
        if field.name == "indicator_id"
        else field
        for field in WDI_GENERIC_CONTRACT.schema.fields
    )
    schema = WDI_GENERIC_CONTRACT.schema.model_copy(update={"fields": fields})
    contract = WDI_GENERIC_CONTRACT.model_copy(update={"connector_schema": schema})
    ref = _create(store, contract=contract)
    assert store.get_manifest(ref).artifact_schema.version == "1.1"
    code = """
import hashlib, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from polisyos.core import artifacts
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.fabric.connectors.contracts import load_source_metric_unit_declaration
from polisyos.fabric.connectors.contracts.source_units import _declaration_json_payload
ref = artifacts.ArtifactRef.model_validate_json(sys.argv[3])
reader = artifacts.FileSystemCAS.open_existing_read_only(Path(sys.argv[2]))
value = load_source_metric_unit_declaration(reader, ref)
raw = to_canonical_bytes(_declaration_json_payload(value), spec=CanonSpec(forbid_floats=False, exclude_none=False))
assert raw == reader.get_bytes(ref)
assert 'sha256:' + hashlib.sha256(raw).hexdigest() == str(ref.artifact_id)
assert Path(sys.modules[load_source_metric_unit_declaration.__module__].__file__).resolve().is_relative_to(Path(sys.argv[1]))
print(value.schema_content_hash)
"""
    source = Path(__file__).resolve().parents[5] / "src"
    for seed in ("1", "42"):
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                code,
                str(source),
                str(tmp_path / "cas"),
                ref.model_dump_json(),
            ],
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        assert completed.stdout.strip() == contract.schema.content_hash


def test_same_schema_cannot_substitute_another_connector_contract(tmp_path: Path) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    other = WDI_GENERIC_CONTRACT.model_copy(update={"contract_id": "worldbank.wdi.other"})
    assert other.schema.identity_key == WDI_GENERIC_CONTRACT.schema.identity_key
    with pytest.raises(ValueError, match="source_unit_source_connector_contract_mismatch"):
        _create(store, contract=other, source=_source())


@pytest.mark.parametrize("kind", [SchemaType.STRING, SchemaType.CATEGORY, SchemaType.BOOLEAN])
def test_declared_physical_unit_requires_a_numeric_measure(
    tmp_path: Path, kind: SchemaType
) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    fields = tuple(
        field.model_copy(update={"data_type": kind}) if field.name == "value" else field
        for field in WDI_GENERIC_CONTRACT.schema.fields
    )
    schema = WDI_GENERIC_CONTRACT.schema.model_copy(update={"fields": fields})
    contract = WDI_GENERIC_CONTRACT.model_copy(update={"connector_schema": schema})
    with pytest.raises(ValueError, match="source_unit_metric_field_scope_mismatch"):
        _create(store, contract=contract)


def test_decimal_measure_remains_a_supported_declared_coordinate(tmp_path: Path) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    fields = tuple(
        field.model_copy(update={"data_type": SchemaType.DECIMAL})
        if field.name == "value"
        else field
        for field in WDI_GENERIC_CONTRACT.schema.fields
    )
    schema = WDI_GENERIC_CONTRACT.schema.model_copy(update={"fields": fields})
    contract = WDI_GENERIC_CONTRACT.model_copy(update={"connector_schema": schema})
    value = load_source_metric_unit_declaration(store, _create(store, contract=contract))
    assert value.connector_contract.schema.get_field("value").data_type is SchemaType.DECIMAL


def test_source_contract_legacy_hash_and_snapshot_are_unchanged() -> None:
    source = _source()
    legacy_payload = source.model_dump(mode="json", by_alias=True, exclude={"created_at"})
    expected = "sha256:" + content_hash(
        to_canonical_bytes(legacy_payload, spec=CanonSpec(forbid_floats=False))
    )
    assert source.content_hash == expected
    before = source.to_snapshot_record()
    new = source.to_canonical_snapshot_record(hash_profile=SOURCE_CONTRACT_FIELD_SET_HASH_PROFILE)
    assert before["contract"] == legacy_payload
    assert source.to_snapshot_record() == before
    assert source.content_hash == expected
    # Empty set fields already had a stable representation; choosing the new
    # profile is explicit even when its physical content hash is equal.
    assert new["contract"] == before["contract"]
    assert new["content_hash"] == before["content_hash"]
    assert new["hash_profile"] == SOURCE_CONTRACT_FIELD_SET_HASH_PROFILE
    assert "hash_profile" not in before
    with pytest.raises(ValueError, match="source_contract_hash_profile_unsupported"):
        source.to_canonical_snapshot_record(hash_profile="other")


def test_legacy_unit_manifest_is_replayed_without_restatement(tmp_path: Path) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    new_ref = _create(store)
    current = load_source_metric_unit_declaration(store, new_ref)
    assert current.source_contract_hash_profile == SOURCE_CONTRACT_FIELD_SET_HASH_PROFILE
    assert current.hash_replay_limitation_codes == ()
    payload = current.model_dump(mode="json")
    payload["schema_version"] = "fabric.source_metric_unit.v1"
    payload.pop("source_contract_hash_profile")
    payload["source_contract_content_hash"] = current.source_contract.content_hash
    legacy_ref = _raw_selected(store, payload, version="1.0")
    before = store.get_bytes(legacy_ref)
    legacy = load_source_metric_unit_declaration(store, legacy_ref)
    assert legacy.source_contract_hash_profile is None
    assert "source_contract_hash_profile" not in legacy.model_dump(mode="json")
    assert legacy.hash_replay_limitation_codes == (
        "source_contract_legacy_hash_portability_not_established",
    )
    assert store.get_bytes(legacy_ref) == before
    assert store.get_manifest(legacy_ref).artifact_schema.version == "1.0"
    with pytest.raises(ValueError):
        load_source_metric_unit_declaration(store, _raw_selected(store, payload, version="1.1"))
    with pytest.raises(ValueError, match="source_unit_hash_profile_version_mismatch"):
        SourceMetricUnitDeclaration.model_validate(
            {**payload, "source_contract_hash_profile": SOURCE_CONTRACT_FIELD_SET_HASH_PROFILE}
        )
    with pytest.raises(ValueError, match="source_unit_hash_profile_version_mismatch"):
        SourceMetricUnitDeclaration.model_validate(
            {**current.model_dump(mode="python"), "source_contract_hash_profile": None}
        )
