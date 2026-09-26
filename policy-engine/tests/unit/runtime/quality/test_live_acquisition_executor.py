"""Behavioral contract for one bounded World Bank acquisition execution."""

from __future__ import annotations

import asyncio
import hashlib
import json
import socket
import threading
from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pandas as pd
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import DataSnapshot, DataSnapshotRef
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.fabric.connectors import (
    ResultSerializer,
    SourceProfileRegistry,
    resolve_connection_config,
)
from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
from polisyos.fabric.data_plane import (
    content_sha256,
    resolve_journal_event_ref,
    resolve_live_attempt_terminals,
)
from polisyos.fabric.data_plane.evidence_journal import (
    AppendOnlyEvidenceJournal,
    EvidenceJournalError,
    _consume_live_acquire_permit,
)
from polisyos.fabric.data_plane.orchestrator import IngestionResult
from polisyos.fabric.evidence import build_evidence_bundle, persist_evidence_bundle
from polisyos.ir.connectors import (
    DataVersion,
    FetchRequest,
    FetchResult,
    QualityTier,
    VersionStrategy,
)
from polisyos.runtime.http.services import (
    acquisition_surface_execution as acquisition_surface_execution_module,
)
from polisyos.runtime.quality import acquisition_executor as acquisition_executor_module
from polisyos.runtime.quality.acquisition_executor import (
    LiveAcquisitionExecutionError,
    LiveCatalogExecutionConstraints,
    execute_live_catalog_acquisition,
)
from tests.unit.data_forge.domains.catalog.knowledge.test_acquisition_authority import (
    _entry,
    _resolver,
    _write_family_receipt,
)
from tests.unit.data_forge.domains.catalog.knowledge.test_acquisition_authority import (
    _family_receipt as _canonical_family_receipt,
)

_ATTEMPT_ID = "n13b-worldbank-government-balance-001"
_CONNECTOR_ID = "worldbank.wdi"
_PROFILE_ID = "worldbank_wdi"
_INDICATOR_ID = "GC.BAL.CASH.GD.ZS"
_COUNTRY_CODE = "UKR"
_START_YEAR = 2023
_END_YEAR = 2024
_PAGE_SIZE = 1000
_URL = "https://api.worldbank.org/v2/country/UKR/indicator/GC.BAL.CASH.GD.ZS"
_PARAMS = {
    "date": "2023:2024",
    "format": "json",
    "page": "1",
    "per_page": "1000",
}


def _spy_on_journal_permit_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[tuple[str, str, str]], list[object]]:
    """Observe the production owner's permit scope and delegate unchanged."""

    original_scope = getattr(
        AppendOnlyEvidenceJournal,
        "live_acquire_permit_scope",
        None,
    )
    if not callable(original_scope):
        pytest.fail("AppendOnlyEvidenceJournal must expose its public permit scope")
    entered: list[tuple[str, str, str]] = []
    yielded_permits: list[object] = []

    @contextmanager
    def _observed_scope(
        journal: AppendOnlyEvidenceJournal,
        **kwargs: Any,
    ) -> Iterator[object]:
        authorization = kwargs["authorization"]
        entered.append(
            (
                str(authorization.attempt_id),
                str(kwargs["connector_id"]),
                str(kwargs["request_dataset_id"]),
            )
        )
        with original_scope(journal, **kwargs) as permit:
            yielded_permits.append(permit)
            yield permit

    monkeypatch.setattr(
        AppendOnlyEvidenceJournal,
        "live_acquire_permit_scope",
        _observed_scope,
    )
    return entered, yielded_permits


def _family_receipt(*, scenario: str = "success") -> dict[str, object]:
    receipt = _canonical_family_receipt(_ATTEMPT_ID)
    carrier = dict(receipt["dry_run_attempts"][0])
    profile = SourceProfileRegistry.get_instance().get(_PROFILE_ID)
    assert profile is not None
    carrier.update(
        {
            "source_profile_family": "worldbank",
            "connection_config_content_sha256": content_sha256(
                resolve_connection_config(profile).to_dict(redact=True)
            ),
            "fetch_request_key": FetchRequest(dataset_id=_INDICATOR_ID).request_key,
        }
    )
    if scenario == "receipt_config_drift":
        carrier["connection_config_content_sha256"] = "sha256:" + "0" * 64
    elif scenario == "receipt_request_drift":
        carrier["fetch_request_key"] = "sha256:" + "0" * 64
    elif scenario == "receipt_profile_family_drift":
        carrier["source_profile_family"] = "forged"
    receipt["dry_run_attempts"] = [carrier]
    return receipt


def _constraints() -> LiveCatalogExecutionConstraints:
    return LiveCatalogExecutionConstraints(
        country_code=_COUNTRY_CODE,
        start_year=_START_YEAR,
        end_year=_END_YEAR,
        page_size=_PAGE_SIZE,
        max_response_bytes=65_536,
        max_decompressed_bytes=65_536,
        timeout_cap_seconds=15.0,
        heartbeat_cap_seconds=5.0,
    )


def _route_closure(
    *,
    variable_id: str = "government.balance",
    region: str = _COUNTRY_CODE,
    data_time: str = "2024",
) -> object:
    """Return the exact route projection consumed by the live binding resolver."""

    return SimpleNamespace(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-acquisition",
        route_id="sha256:" + "1" * 64,
        design_problem=SimpleNamespace(
            jurisdiction_time=SimpleNamespace(region=region, data_time=data_time)
        ),
        planner_record=SimpleNamespace(
            gap_type="data_snapshot_release",
            requirement_family="data_requirement",
            requirement_schema_version=("policyos.runtime.l1_variable_availability_gap.v1"),
            missing_requirement_fields=(
                f"canonical_variable_observations:{variable_id}",
            ),
            recommended_strategy="production_snapshot_build",
        ),
    )


def _normalized_rows(*, adjacent: str | None = None) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {
            "country_code": _COUNTRY_CODE,
            "country_name": "Ukraine",
            "indicator_id": _INDICATOR_ID,
            "indicator_name": "Cash surplus/deficit (% of GDP)",
            "year": 2023,
            "value": -18.2,
            "unit": "% of GDP",
            "decimal": 1,
        },
        {
            "country_code": _COUNTRY_CODE,
            "country_name": "Ukraine",
            "indicator_id": _INDICATOR_ID,
            "indicator_name": "Cash surplus/deficit (% of GDP)",
            "year": 2024,
            "value": -17.1,
            "unit": "% of GDP",
            "decimal": 1,
        },
    ]
    if adjacent == "indicator":
        rows.append(
            {
                **rows[-1],
                "indicator_id": "FP.CPI.TOTL",
                "indicator_name": "Consumer price index",
                "value": 128.4,
            }
        )
    elif adjacent == "country":
        rows.append({**rows[-1], "country_code": "POL", "country_name": "Poland"})
    elif adjacent == "year":
        rows.append({**rows[-1], "year": 2022})
    return rows


def _raw_body(
    rows: list[dict[str, object]],
    *,
    per_page: int = _PAGE_SIZE,
    total: int | None = None,
) -> bytes:
    records = [
        {
            "countryiso3code": row["country_code"],
            "country": {"id": "UA", "value": row["country_name"]},
            "indicator": {
                "id": row["indicator_id"],
                "value": row["indicator_name"],
            },
            "date": str(row["year"]),
            "value": row["value"],
            "unit": row["unit"],
            "decimal": row["decimal"],
        }
        for row in rows
    ]
    return json.dumps(
        [
            {
                "page": 1,
                "pages": 1,
                "per_page": per_page,
                "total": len(records) if total is None else total,
            },
            records,
        ],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _fetch_result(
    rows: list[dict[str, object]],
    *,
    body: bytes,
) -> FetchResult[pd.DataFrame]:
    fetched_at = datetime.now(UTC)
    body_sha256 = "sha256:" + hashlib.sha256(body).hexdigest()
    frame = pd.DataFrame(rows)
    return FetchResult(
        data=frame,
        row_count=len(frame),
        schema_id="worldbank.wdi.generic",
        schema_version="2.0.0",
        version=DataVersion(
            strategy=VersionStrategy.CONTENT_HASH,
            value=body_sha256,
            timestamp=fetched_at,
            content_hash=body_sha256,
        ),
        fetched_at=fetched_at,
        completeness=1.0,
        quality_tier=QualityTier.GOLD,
        has_more=False,
        next_page_token=None,
    )


def _manifest_dataset(manifest: object) -> object:
    datasets = getattr(manifest, "datasets", None)
    if datasets is None and isinstance(manifest, Mapping):
        datasets = manifest.get("datasets")
    assert isinstance(datasets, list)
    assert len(datasets) == 1
    return datasets[0]


def _dataset_value(dataset: object, key: str) -> object:
    if isinstance(dataset, Mapping):
        return dataset[key]
    return getattr(dataset, key)


def _fetch_request_from_manifest(manifest: object) -> FetchRequest:
    dataset = _manifest_dataset(manifest)
    filters = _dataset_value(dataset, "filters")
    assert isinstance(filters, Mapping)
    normalized_filters = tuple(
        (str(key), tuple(str(value) for value in values)) for key, values in sorted(filters.items())
    )
    return FetchRequest(
        dataset_id=str(_dataset_value(dataset, "dataset_id")),
        date_start=datetime.fromisoformat(str(_dataset_value(dataset, "date_start"))).replace(
            tzinfo=UTC
        ),
        date_end=datetime.fromisoformat(str(_dataset_value(dataset, "date_end"))).replace(
            tzinfo=UTC
        ),
        filters=normalized_filters,
        page_size=int(_dataset_value(dataset, "page_size")),
        retryable=bool(_dataset_value(dataset, "retryable")),
    )


class _OrchestratedWorldBankStub:
    """Emulate only Fabric's observer/sink contract; never open a network socket."""

    def __init__(
        self,
        *,
        scenario: str,
        baseline_path: Path,
        journal_path: Path,
    ) -> None:
        self.scenario = scenario
        self.baseline_path = baseline_path
        self.journal_path = journal_path
        self.calls: list[dict[str, object]] = []
        self.raw_visible_before_sink = False
        self.cas_root: Path | None = None

    def __call__(self, **kwargs: object) -> IngestionResult:
        self.calls.append(dict(kwargs))
        self.cas_root = Path(str(kwargs["cas_root"]))
        manifest = kwargs["connector_manifest"]
        observer = kwargs.get("raw_http_response_observer")
        sink = kwargs.get("raw_result_sink")
        rows = _normalized_rows(
            adjacent=(
                self.scenario.removeprefix("adjacent_")
                if self.scenario.startswith("adjacent_")
                else None
            )
        )
        result_rows = [dict(row) for row in rows]
        if self.scenario == "result_value_drift":
            result_rows[0]["value"] = -999.0
        elif self.scenario == "result_unit_drift":
            result_rows[0]["unit"] = "percentage points"
        elif self.scenario == "result_decimal_drift":
            result_rows[0]["decimal"] = 7
        elif self.scenario == "result_name_drift":
            result_rows[0]["indicator_name"] = "Fabricated government balance"
        body = _raw_body(
            rows,
            per_page=(999 if self.scenario == "metadata_per_page_drift" else _PAGE_SIZE),
            total=(999 if self.scenario == "metadata_total_drift" else None),
        )
        result = _fetch_result(result_rows, body=body)
        if self.scenario == "fabricated_result_version":
            forged_hash = "sha256:" + "0" * 64
            result = result.model_copy(
                update={
                    "version": result.version.model_copy(
                        update={"value": forged_hash, "content_hash": forged_hash}
                    )
                }
            )
        fetch_request = _fetch_request_from_manifest(manifest)

        if self.scenario != "omit_observer":
            assert observer is not None
            url, params = self._transport_projection()
            observer.before_request(_CONNECTOR_ID, url, params)  # type: ignore[attr-defined]
            on_headers = getattr(observer, "on_response_headers", None)
            if callable(on_headers):
                on_headers(
                    _CONNECTOR_ID,
                    url,
                    params,
                    200,
                    {"content-type": "application/json"},
                )
            on_progress = getattr(observer, "on_body_progress", None)
            if callable(on_progress):
                on_progress(_CONNECTOR_ID, url, params, len(body))

            if self.scenario == "sink_before_raw":
                assert callable(sink)
                sink(_CONNECTOR_ID, _INDICATOR_ID, fetch_request, result)

            observer.on_raw_response(  # type: ignore[attr-defined]
                _CONNECTOR_ID,
                url,
                params,
                200,
                {"content-type": "application/json"},
                body,
            )

            if self.scenario in {"retry_second_call", "renamed_second_call"}:
                retry_url = (
                    url
                    if self.scenario == "retry_second_call"
                    else url.replace(_INDICATOR_ID, "FP.CPI.TOTL")
                )
                observer.before_request(  # type: ignore[attr-defined]
                    _CONNECTOR_ID,
                    retry_url,
                    params,
                )

        if self.scenario != "omit_sink":
            assert callable(sink)
            if self.journal_path.is_file():
                events = _journal_events(self.journal_path)
                self.raw_visible_before_sink = any(
                    event.get("event_kind") == "raw_response" for event in events
                )
            sink(_CONNECTOR_ID, _INDICATOR_ID, fetch_request, result)

        if self.scenario == "baseline_mutation":
            with self.baseline_path.open("ab") as handle:
                handle.write(b"n13b-baseline-mutation-probe")
        if self.scenario == "baseline_mutation_then_error":
            with self.baseline_path.open("ab") as handle:
                handle.write(b"n13b-baseline-mutation-probe")
            raise RuntimeError("simulated transport failure after baseline mutation")

        store = FileSystemCAS(self.cas_root)
        serialized, media_type = ResultSerializer.serialize(result)
        data_ref = store.put_bytes(
            serialized,
            ArtifactWriteOptions(
                kind="fabric.connector_cache.payload",
                media_type=media_type,
            ),
        )
        evidence_ref = persist_evidence_bundle(
            store,
            build_evidence_bundle(
                sources=[data_ref],
                notes=["network-free orchestrated WDI test"],
            ),
        )
        snapshot = DataSnapshot(
            data_ref=data_ref,
            evidence_ref=evidence_ref,
            stats={"datasets_fetched": 1, "source": "orchestrated_ingestion:test"},
            notes=["fabric.data_plane.orchestrator", "datasets=1"],
        )
        snapshot_artifact = store.put_json(
            snapshot,
            ArtifactWriteOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.core.DataSnapshot",
                    version="0.2.0",
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        return IngestionResult(
            evidence_bundle_ref=evidence_ref,
            data_snapshot_ref=DataSnapshotRef(artifact_id=snapshot_artifact.artifact_id),
            datasets_fetched=1,
        )

    def _transport_projection(self) -> tuple[str, dict[str, str]]:
        url = _URL
        params = dict(_PARAMS)
        if self.scenario == "wrong_host":
            url = url.replace("api.worldbank.org", "attacker.invalid")
        elif self.scenario == "wrong_path":
            url = url.replace("/v2/country/", "/v1/series/")
        elif self.scenario == "wrong_indicator":
            url = url.replace(_INDICATOR_ID, "FP.CPI.TOTL")
        elif self.scenario == "wrong_country":
            url = url.replace("/UKR/", "/POL/")
        elif self.scenario == "wrong_year":
            params["date"] = "2022:2024"
        return url, params


def _journal_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _assert_error_code(exc: BaseException, expected: str) -> None:
    assert getattr(exc, "code", None) == expected or expected in str(exc)


def _failure_terminal(path: Path):
    terminals = resolve_live_attempt_terminals(path)
    assert len(terminals) == 1
    return terminals[0]


def _resolved_live_worldbank_authority(tmp_path: Path) -> tuple[object, object]:
    repo_root = tmp_path / "repo"
    entry = _entry()
    receipt_provision = _write_family_receipt(
        repo_root,
        entry_id=entry.entry_id,
        attempt_id=_ATTEMPT_ID,
        receipt=_family_receipt(),
    )
    authority, entry = _resolver(
        repo_root,
        authority_entry=entry,
        live_harness_receipts=(receipt_provision,),
    )
    return authority, entry


def _run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    scenario: str = "success",
    constraints: LiveCatalogExecutionConstraints | None = None,
    authority_entry: object | None = None,
    execution_dependencies: dict[str, object] | None = None,
    cache_namespace: str | None = None,
) -> tuple[object, object, _OrchestratedWorldBankStub, Path]:
    repo_root = tmp_path / "repo"
    entry = authority_entry or _entry()
    receipt = _family_receipt(scenario=scenario)
    receipt_provision = _write_family_receipt(
        repo_root,
        entry_id=entry.entry_id,
        attempt_id=_ATTEMPT_ID,
        receipt=receipt,
    )
    authority, entry = _resolver(
        repo_root,
        authority_entry=entry,
        live_harness_receipts=(receipt_provision,),
    )
    journal_path = tmp_path / "journal.jsonl"
    stub = _OrchestratedWorldBankStub(
        scenario=scenario,
        baseline_path=authority.baseline_path,
        journal_path=journal_path,
    )

    async def _forbid_direct_fetch(*args: object, **kwargs: object) -> object:
        del args, kwargs
        pytest.fail("live acquisition bypassed run_orchestrated_ingestion")

    monkeypatch.setattr(WorldBankConnector, "fetch", _forbid_direct_fetch)
    monkeypatch.setattr(
        acquisition_executor_module,
        "run_orchestrated_ingestion",
        stub,
    )

    cas_root = tmp_path / "cas"
    dependencies = dict(execution_dependencies or {})
    if "artifact_store" not in dependencies:
        dependencies["artifact_store"] = FileSystemCAS(cas_root)
    result = execute_live_catalog_acquisition(
        authority=authority,
        entry_id=entry.entry_id,
        attempt_id=_ATTEMPT_ID,
        constraints=constraints or _constraints(),
        journal_path=journal_path,
        cas_root=cas_root,
        cache_namespace=cache_namespace,
        **dependencies,
    )
    return authority, result, stub, journal_path


def _entry_with_temporal_scope(
    temporal_start: str | None,
    temporal_end: str | None,
) -> object:
    values = _entry().model_dump(mode="python", exclude={"entry_id"})
    values["schema_columns"] = tuple(
        catalog_read_api.AuthoritySchemaColumn.model_validate(column)
        for column in values["schema_columns"]
    )
    values["temporal_start"] = temporal_start
    values["temporal_end"] = temporal_end
    return catalog_read_api.build_authority_entry(**values)


def _sibling_entry_with_same_target() -> object:
    values = _entry().model_dump(mode="python", exclude={"entry_id"})
    values["schema_columns"] = tuple(
        catalog_read_api.AuthoritySchemaColumn.model_validate(column)
        for column in values["schema_columns"]
    )
    values.update(
        {
            "landing_dataset_id": "acquisition.worldbank.government_balance.sibling",
            "landing_distribution_id": (
                "acquisition.worldbank.government_balance.sibling.json"
            ),
            "title": "Sibling government balance authority",
        }
    )
    return catalog_read_api.build_authority_entry(**values)


def test_route_binding_resolves_one_content_bound_world_bank_attempt(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    entry = _entry()
    receipt_provision = _write_family_receipt(
        repo_root,
        entry_id=entry.entry_id,
        attempt_id=_ATTEMPT_ID,
        receipt=_family_receipt(),
    )
    authority, entry = _resolver(
        repo_root,
        authority_entry=entry,
        live_harness_receipts=(receipt_provision,),
    )
    registry = catalog_read_api.AcquisitionAuthorityRegistry.model_validate_json(
        authority.registry_path.read_bytes()
    )

    bindings = (
        acquisition_surface_execution_module.resolve_world_bank_wdi_route_execution_bindings(
            closure=_route_closure(),
            authority=authority,
            registry=registry,
            provision=authority.provision,
            provision_content_sha256=authority.provision_content_sha256,
        )
    )

    assert len(bindings) == 1
    binding = bindings[0]
    assert binding.authority_entry_id == entry.entry_id
    assert binding.authority_provision_id == authority.provision.provision_id
    assert binding.authority_registry_content_sha256 == registry.content_sha256
    assert binding.target_variable == "government.balance"
    assert binding.connector_id == "worldbank.wdi"
    assert binding.attempt_id == _ATTEMPT_ID
    assert binding.constraints == LiveCatalogExecutionConstraints(
        country_code="UKR",
        start_year=2024,
        end_year=2024,
        page_size=1000,
        max_response_bytes=65_536,
        max_decompressed_bytes=65_536,
        timeout_cap_seconds=15.0,
        heartbeat_cap_seconds=5.0,
    )


@pytest.mark.parametrize(
    ("route", "expected_code"),
    [
        (
            SimpleNamespace(
                **{
                    **vars(_route_closure()),
                    "planner_record": SimpleNamespace(
                        **{
                            **vars(_route_closure().planner_record),
                            "gap_type": "legal_corpus_coverage",
                        }
                    ),
                }
            ),
            "live_route_requirement_shape_invalid",
        ),
        (
            SimpleNamespace(
                **{
                    **vars(_route_closure()),
                    "planner_record": SimpleNamespace(
                        **{
                            **vars(_route_closure().planner_record),
                            "missing_requirement_fields": (),
                        }
                    ),
                }
            ),
            "live_route_variable_requirement_invalid",
        ),
        (
            SimpleNamespace(
                **{
                    **vars(_route_closure()),
                    "planner_record": SimpleNamespace(
                        **{
                            **vars(_route_closure().planner_record),
                            "missing_requirement_fields": (
                                "canonical_variable_observations:government.balance",
                                "canonical_variable_observations:inflation",
                            ),
                        }
                    ),
                }
            ),
            "live_route_variable_requirement_invalid",
        ),
    ],
)
def test_route_binding_rejects_bad_route_shape_before_authority_resolution(
    route: object,
    expected_code: str,
) -> None:
    class _AuthorityMustNotResolve:
        def resolve(self, entry_id: str) -> object:
            pytest.fail(f"authority resolved for rejected route: {entry_id}")

    with pytest.raises(LiveAcquisitionExecutionError) as exc_info:
        acquisition_surface_execution_module.resolve_world_bank_wdi_route_execution_bindings(
            closure=route,
            authority=_AuthorityMustNotResolve(),
            registry=SimpleNamespace(entries=()),
            provision=SimpleNamespace(),
            provision_content_sha256="sha256:" + "0" * 64,
        )

    assert exc_info.value.code == expected_code


def test_route_binding_rejects_missing_and_out_of_scope_authority(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    entry = _entry()
    receipt_provision = _write_family_receipt(
        repo_root,
        entry_id=entry.entry_id,
        attempt_id=_ATTEMPT_ID,
        receipt=_family_receipt(),
    )
    authority, _ = _resolver(
        repo_root,
        authority_entry=entry,
        live_harness_receipts=(receipt_provision,),
    )
    registry = catalog_read_api.AcquisitionAuthorityRegistry.model_validate_json(
        authority.registry_path.read_bytes()
    )
    common = {
        "authority": authority,
        "registry": registry,
        "provision": authority.provision,
        "provision_content_sha256": authority.provision_content_sha256,
    }

    cases = (
        (_route_closure(variable_id="inflation"), "live_route_authority_entry_missing"),
        (_route_closure(region="POL"), "live_request_outside_authority_countries"),
        (_route_closure(data_time="2025"), "live_request_outside_authority_period"),
        (_route_closure(data_time="2024-Q1"), "live_route_data_time_invalid"),
    )
    for route, expected_code in cases:
        with pytest.raises(LiveAcquisitionExecutionError) as exc_info:
            acquisition_surface_execution_module.resolve_world_bank_wdi_route_execution_bindings(
                closure=route,
                **common,
            )
        assert exc_info.value.code == expected_code


def test_route_binding_requires_a_reopenable_provisioned_attempt(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    authority, _ = _resolver(repo_root, authority_entry=_entry())
    registry = catalog_read_api.AcquisitionAuthorityRegistry.model_validate_json(
        authority.registry_path.read_bytes()
    )

    with pytest.raises(LiveAcquisitionExecutionError) as exc_info:
        acquisition_surface_execution_module.resolve_world_bank_wdi_route_execution_bindings(
            closure=_route_closure(),
            authority=authority,
            registry=registry,
            provision=authority.provision,
            provision_content_sha256=authority.provision_content_sha256,
        )

    assert exc_info.value.code == "live_route_authority_attempt_missing"


def test_route_binding_rejects_ambiguous_entry_and_owner_drift(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    entry = _entry()
    receipt_provision = _write_family_receipt(
        repo_root,
        entry_id=entry.entry_id,
        attempt_id=_ATTEMPT_ID,
        receipt=_family_receipt(),
    )
    authority, _ = _resolver(
        repo_root,
        authority_entry=entry,
        live_harness_receipts=(receipt_provision,),
    )
    registry = catalog_read_api.AcquisitionAuthorityRegistry.model_validate_json(
        authority.registry_path.read_bytes()
    )
    common = {
        "closure": _route_closure(),
        "authority": authority,
        "provision": authority.provision,
        "provision_content_sha256": authority.provision_content_sha256,
    }

    ambiguous = catalog_read_api.build_authority_registry(
        baseline_content_sha256=registry.baseline_content_sha256,
        l5_measurement_registry_sha256=registry.l5_measurement_registry_sha256,
        entries=(entry, _sibling_entry_with_same_target()),
    )
    with pytest.raises(LiveAcquisitionExecutionError) as ambiguous_error:
        acquisition_surface_execution_module.resolve_world_bank_wdi_route_execution_bindings(
            registry=ambiguous,
            **common,
        )
    assert ambiguous_error.value.code == "live_route_authority_entry_ambiguous"

    with pytest.raises(LiveAcquisitionExecutionError) as registry_drift:
        acquisition_surface_execution_module.resolve_world_bank_wdi_route_execution_bindings(
            registry=registry.model_copy(
                update={"content_sha256": "sha256:" + "0" * 64}
            ),
            **common,
        )
    assert registry_drift.value.code == "live_route_authority_registry_drift"

    with pytest.raises(LiveAcquisitionExecutionError) as provision_drift:
        acquisition_surface_execution_module.resolve_world_bank_wdi_route_execution_bindings(
            registry=registry,
            **{
                **common,
                "provision_content_sha256": "sha256:" + "0" * 64,
            },
        )
    assert provision_drift.value.code == "live_route_authority_provision_drift"

    receipt_path = repo_root / receipt_provision["receipt_owner_ref"].removeprefix("repo://")
    receipt_path.write_text("{}", encoding="utf-8")
    with pytest.raises(LiveAcquisitionExecutionError) as receipt_drift:
        acquisition_surface_execution_module.resolve_world_bank_wdi_route_execution_bindings(
            registry=registry,
            **common,
        )
    assert receipt_drift.value.code == "live_route_authority_attempt_unresolved"


def test_route_binding_rejects_non_world_bank_connector_before_attempt_resolution(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    entry = _entry()
    authority, _ = _resolver(repo_root, authority_entry=entry)
    registry = catalog_read_api.AcquisitionAuthorityRegistry.model_validate_json(
        authority.registry_path.read_bytes()
    )
    resolved = authority.resolve(entry.entry_id)
    drifted = resolved.model_copy(
        update={
            "registration": resolved.registration.model_copy(
                update={"connector_id": "another.connector"}
            )
        }
    )
    authority_view = SimpleNamespace(
        resolve=lambda _entry_id: drifted,
        resolve_live_harness_receipt=lambda *_args: pytest.fail(
            "out-of-scope connector reached attempt resolution"
        ),
    )

    with pytest.raises(LiveAcquisitionExecutionError) as exc_info:
        acquisition_surface_execution_module.resolve_world_bank_wdi_route_execution_bindings(
            closure=_route_closure(),
            authority=authority_view,
            registry=registry,
            provision=authority.provision,
            provision_content_sha256=authority.provision_content_sha256,
        )

    assert exc_info.value.code == "live_route_connector_family_out_of_scope"


def test_live_executor_consults_injected_registry_and_reopens_injected_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.services.control_registry_providers import (
        resolve_control_registry_providers,
    )

    profile = SourceProfileRegistry.get_instance().get(_PROFILE_ID)
    requested_profiles: list[str] = []

    class Profiles:
        def get(self, profile_id: str) -> object:
            requested_profiles.append(profile_id)
            return profile

        def list_all(self) -> list[object]:
            return [profile]

        def list_by_family(self, connector_family: str) -> list[object]:
            return [profile] if connector_family == "worldbank" else []

    class RecordingStore(FileSystemCAS):
        def get_bytes(self, artifact_id):
            reopened.append(str(artifact_id))
            return super().get_bytes(artifact_id)

    reopened: list[str] = []
    store = RecordingStore(tmp_path / "cas")
    providers = resolve_control_registry_providers(source_profiles=Profiles())
    _authority, evidence, _stub, _journal = _run(
        tmp_path,
        monkeypatch,
        execution_dependencies={"artifact_store": store, "registry_providers": providers},
    )

    assert requested_profiles == [_PROFILE_ID]
    assert str(evidence.data_snapshot_ref.artifact_id) in reopened
    assert str(evidence.normalized_data_artifact_id) in reopened
    assert store.has(evidence.raw_artifact_id)
    assert evidence.transport_trace.raw_evidence_ref == evidence.raw_evidence_ref


def test_live_executor_does_not_fall_back_when_injected_profile_is_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http.services.control_registry_providers import (
        resolve_control_registry_providers,
    )

    class AbsentProfiles:
        def get(self, profile_id: str) -> None:
            return None

        def list_all(self) -> list[object]:
            return []

        def list_by_family(self, connector_family: str) -> list[object]:
            return []

    providers = resolve_control_registry_providers(source_profiles=AbsentProfiles())
    with pytest.raises(LiveAcquisitionExecutionError, match="live_source_profile_unresolved"):
        _run(
            tmp_path,
            monkeypatch,
            execution_dependencies={
                "artifact_store": None,
                "registry_providers": providers,
            },
        )
    assert not (tmp_path / "journal.jsonl").exists()
    assert not (tmp_path / "cas").exists()


def test_live_executor_rejects_an_injected_store_with_different_artifact_backing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path / "other-cas")

    with pytest.raises(LiveAcquisitionExecutionError) as refusal:
        _run(tmp_path, monkeypatch, execution_dependencies={"artifact_store": store})

    events = _journal_events(tmp_path / "journal.jsonl")
    terminals = [event for event in events if event["event_kind"] == "live_attempt_terminal"]
    assert len(terminals) == 1
    assert terminals[0]["failure_code"] == refusal.value.code
    assert terminals[0]["failure_code"] != "measured_pending_passport"
    assert terminals[0]["response_admitted"] is False


def test_live_executor_requires_runtime_store_before_journaling_or_egress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    entry = _entry()
    receipt = _write_family_receipt(
        repo_root,
        entry_id=entry.entry_id,
        attempt_id=_ATTEMPT_ID,
        receipt=_family_receipt(),
    )
    authority, entry = _resolver(
        repo_root,
        authority_entry=entry,
        live_harness_receipts=(receipt,),
    )
    journal_path = tmp_path / "journal.jsonl"

    def _forbid_orchestrator(**_kwargs: object) -> object:
        pytest.fail("missing runtime store reached live ingestion")

    monkeypatch.setattr(
        acquisition_executor_module,
        "run_orchestrated_ingestion",
        _forbid_orchestrator,
    )

    with pytest.raises(LiveAcquisitionExecutionError) as refusal:
        execute_live_catalog_acquisition(
            authority=authority,
            entry_id=entry.entry_id,
            attempt_id=_ATTEMPT_ID,
            constraints=_constraints(),
            journal_path=journal_path,
            cas_root=tmp_path / "cas",
        )

    assert refusal.value.code == "live_runtime_artifact_store_required"
    assert not journal_path.exists()


def test_live_executor_forwards_route_cache_namespace_to_orchestration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    namespace = "connector_cache/routes/" + "a" * 64

    _authority, _evidence, stub, _journal_path = _run(
        tmp_path,
        monkeypatch,
        cache_namespace=namespace,
    )

    assert len(stub.calls) == 1
    assert stub.calls[0]["cache_namespace"] == namespace


def test_live_executor_uses_orchestration_and_returns_reopenable_one_call_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority, evidence, stub, journal_path = _run(tmp_path, monkeypatch)

    assert len(stub.calls) == 1
    call = stub.calls[0]
    assert call["produce_snapshot"] is True
    assert hasattr(call["raw_http_response_observer"], "before_request")
    assert callable(call["raw_result_sink"])
    assert stub.raw_visible_before_sink is True
    dataset = _manifest_dataset(call["connector_manifest"])
    assert _dataset_value(dataset, "connector_id") == _CONNECTOR_ID
    assert _dataset_value(dataset, "dataset_id") == _INDICATOR_ID
    assert _dataset_value(dataset, "filters") == {"country": [_COUNTRY_CODE]}
    assert _dataset_value(dataset, "date_start") == "2023-01-01"
    assert _dataset_value(dataset, "date_end") == "2024-12-31"
    assert _dataset_value(dataset, "page_size") == _PAGE_SIZE
    assert _dataset_value(dataset, "retryable") is False
    connection = call["connection_config"]
    assert connection.url == "https://api.worldbank.org/v2"
    assert connection.max_retries == 1
    assert connection.max_connections == 1

    assert evidence.authorization.request_variables == (_INDICATOR_ID,)
    assert evidence.call_count == 1
    assert evidence.variable_count == 1
    assert evidence.page_count == 1
    assert evidence.transport_trace.url == _URL
    assert evidence.transport_trace.params == _PARAMS
    assert evidence.transport_trace.heartbeat_phases == (
        "attempt_started",
        "response_headers",
        "body_progress",
    )
    assert resolve_journal_event_ref(evidence.request_ref)["request"]["request_variables"] == [
        _INDICATOR_ID
    ]
    assert [event["event_kind"] for event in _journal_events(journal_path)] == [
        "request",
        "transport_attempt",
        "heartbeat",
        "heartbeat",
        "heartbeat",
        "raw_response",
        "classification",
        "live_attempt_terminal",
    ]
    assert stub.cas_root is not None
    entry_id = resolve_journal_event_ref(evidence.request_ref)["request"]["authority_entry_id"]
    reopened = authority.resolve_live_source_execution(
        entry_id,
        evidence,
        FileSystemCAS(stub.cas_root),
    )
    assert reopened.row_count == 2
    assert set(reopened.data["indicator_id"]) == {_INDICATOR_ID}
    assert set(reopened.data["country_code"]) == {_COUNTRY_CODE}
    assert set(reopened.data["year"]) == {_START_YEAR, _END_YEAR}


@pytest.mark.parametrize(
    ("scenario", "expected_code"),
    [
        ("omit_observer", "live_result_before_raw_evidence"),
        ("omit_sink", "live_result_sink_not_invoked"),
        ("sink_before_raw", "live_result_before_raw_evidence"),
    ],
)
def test_live_executor_requires_observer_and_sink_handshakes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    expected_code: str,
) -> None:
    with pytest.raises(Exception) as exc_info:
        _run(tmp_path, monkeypatch, scenario=scenario)

    _assert_error_code(exc_info.value, expected_code)
    terminal = _failure_terminal(tmp_path / "journal.jsonl")
    assert terminal.failure_code == expected_code
    if scenario == "omit_sink":
        assert terminal.raw_evidence_ref is not None
    else:
        assert terminal.raw_evidence_ref is None


@pytest.mark.parametrize(
    "scenario",
    ["wrong_host", "wrong_path", "wrong_indicator", "wrong_country", "wrong_year"],
)
def test_live_executor_rejects_any_transport_scope_drift_before_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    journal_path = tmp_path / "journal.jsonl"

    with pytest.raises(Exception) as exc_info:
        _run(tmp_path, monkeypatch, scenario=scenario)

    _assert_error_code(exc_info.value, "live_transport_request_drift")
    events = _journal_events(journal_path)
    assert sum(event["event_kind"] == "transport_attempt" for event in events) == 1
    assert all(event["event_kind"] != "raw_response" for event in events)
    terminal = _failure_terminal(journal_path)
    assert terminal.failure_code == "live_transport_request_drift"
    assert terminal.raw_evidence_ref is None


@pytest.mark.parametrize("scenario", ["retry_second_call", "renamed_second_call"])
def test_live_executor_journals_and_rejects_every_second_transport_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    journal_path = tmp_path / "journal.jsonl"

    with pytest.raises(Exception) as exc_info:
        _run(tmp_path, monkeypatch, scenario=scenario)

    _assert_error_code(exc_info.value, "live_call_budget_exceeded")
    events = _journal_events(journal_path)
    assert sum(event["event_kind"] == "transport_attempt" for event in events) == 2
    terminal = _failure_terminal(journal_path)
    assert terminal.failure_code == "live_call_budget_exceeded"
    assert terminal.raw_evidence_ref is not None


@pytest.mark.parametrize(
    "scenario",
    ["adjacent_indicator", "adjacent_country", "adjacent_year"],
)
def test_live_executor_rejects_adjacent_normalized_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    with pytest.raises(Exception) as exc_info:
        _run(tmp_path, monkeypatch, scenario=scenario)

    _assert_error_code(exc_info.value, "live_normalized_scope_drift")


def test_live_executor_rejects_baseline_mutation_after_orchestration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(Exception) as exc_info:
        _run(tmp_path, monkeypatch, scenario="baseline_mutation")

    _assert_error_code(exc_info.value, "live_baseline_identity_drift")


def test_live_executor_rejects_baseline_mutation_when_orchestration_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(Exception) as exc_info:
        _run(tmp_path, monkeypatch, scenario="baseline_mutation_then_error")

    _assert_error_code(exc_info.value, "live_baseline_identity_drift")


def test_live_executor_rejects_fabricated_fetch_result_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(Exception) as exc_info:
        _run(tmp_path, monkeypatch, scenario="fabricated_result_version")

    _assert_error_code(exc_info.value, "live_normalized_contract_drift")


def test_live_executor_rejects_request_outside_owner_temporal_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outside = _constraints().model_copy(update={"start_year": 2019})

    with pytest.raises(Exception) as exc_info:
        _run(tmp_path, monkeypatch, constraints=outside)

    _assert_error_code(exc_info.value, "live_request_outside_authority_period")


def test_live_executor_accepts_request_when_catalog_temporal_bounds_are_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, evidence, stub, _ = _run(
        tmp_path,
        monkeypatch,
        authority_entry=_entry_with_temporal_scope(None, None),
    )

    assert evidence.call_count == 1
    assert len(stub.calls) == 1


def test_live_executor_rejects_half_declared_temporal_authority_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(Exception) as exc_info:
        _run(
            tmp_path,
            monkeypatch,
            authority_entry=_entry_with_temporal_scope(None, "2024"),
        )

    _assert_error_code(exc_info.value, "live_authority_temporal_scope_invalid")


def test_live_executor_rejects_country_outside_owner_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outside = _constraints().model_copy(update={"country_code": "POL"})

    with pytest.raises(Exception) as exc_info:
        _run(tmp_path, monkeypatch, constraints=outside)

    _assert_error_code(exc_info.value, "live_request_outside_authority_countries")


@pytest.mark.parametrize(
    ("scenario", "expected_code"),
    [
        ("receipt_config_drift", "live_harness_connection_config_drift"),
        ("receipt_request_drift", "live_harness_fetch_request_drift"),
        ("receipt_profile_family_drift", "live_harness_profile_family_drift"),
    ],
)
def test_live_executor_recomputes_every_selected_harness_carrier_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    expected_code: str,
) -> None:
    with pytest.raises(Exception) as exc_info:
        _run(tmp_path, monkeypatch, scenario=scenario)

    _assert_error_code(exc_info.value, expected_code)


@pytest.mark.parametrize(
    "scenario",
    [
        "result_value_drift",
        "result_unit_drift",
        "result_decimal_drift",
        "result_name_drift",
    ],
)
def test_live_executor_rejects_any_normalized_field_not_derived_from_raw(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    with pytest.raises(Exception) as exc_info:
        _run(tmp_path, monkeypatch, scenario=scenario)

    _assert_error_code(exc_info.value, "live_normalized_raw_projection_drift")
    terminal = _failure_terminal(tmp_path / "journal.jsonl")
    assert terminal.failure_code == "live_normalized_raw_projection_drift"
    assert terminal.raw_evidence_ref is not None


@pytest.mark.parametrize(
    "scenario",
    ["metadata_per_page_drift", "metadata_total_drift"],
)
def test_live_executor_binds_raw_page_metadata_to_the_full_denominator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    with pytest.raises(Exception) as exc_info:
        _run(tmp_path, monkeypatch, scenario=scenario)

    _assert_error_code(exc_info.value, "live_raw_page_metadata_drift")


def test_live_executor_runs_real_orchestrator_and_connector_with_intercepted_transport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove the real Fabric/WorldBank handshake without opening a socket."""

    import aiohttp

    from polisyos.fabric.connectors.pool import ConnectionPool

    scope_entries, scoped_permits = _spy_on_journal_permit_scope(monkeypatch)
    pool_permits: list[object] = []
    repo_root = tmp_path / "repo"
    entry = _entry()
    receipt = _family_receipt()
    receipt_provision = _write_family_receipt(
        repo_root,
        entry_id=entry.entry_id,
        attempt_id=_ATTEMPT_ID,
        receipt=receipt,
    )
    authority, entry = _resolver(
        repo_root,
        authority_entry=entry,
        live_harness_receipts=(receipt_provision,),
    )
    body = _raw_body(_normalized_rows())
    transport_calls: list[tuple[str, str, dict[str, str]]] = []
    health_checks: list[str] = []
    original_health_check = WorldBankConnector.health_check

    async def _track_health_check(self: WorldBankConnector, handle: object):
        health_checks.append(str(getattr(handle, "session_id", "unknown")))
        return await original_health_check(self, handle)

    original_acquire = ConnectionPool._acquire_with_live_permit

    async def _attempt_mutation_then_acquire(
        pool: ConnectionPool,
        permit: object,
        *,
        connector_id: str,
        dataset_id: str,
    ) -> Any:
        pool_permits.append(permit)
        issued = AppendOnlyEvidenceJournal._live_acquire_permits.get(permit)
        assert issued is not None and issued[1] == "issued"
        binding = issued[0]
        assert binding.journal_path == (tmp_path / "journal.jsonl").as_posix()
        assert binding.journal.path.as_posix() == binding.journal_path
        assert binding.attempt_id == _ATTEMPT_ID
        assert binding.connector_id == _CONNECTOR_ID
        assert binding.dataset_id == _INDICATOR_ID
        bound_event = resolve_journal_event_ref(binding.request_ref)
        assert bound_event["event_kind"] == "request"
        assert bound_event["attempt_id"] == _ATTEMPT_ID
        assert bound_event["request_sha256"] == binding.request_sha256
        assert isinstance(bound_event["request"], Mapping)
        assert bound_event["request"]["request_dataset_id"] == _INDICATOR_ID
        forged_fields = {
            "_journal": object(),
            "_journal_path": "/tmp/forged-journal.jsonl",
            "_journal_sha256": "sha256:" + "0" * 64,
            "_request_ref": object(),
            "_attempt_id": "forged-attempt",
            "_connector_id": "forged.connector",
            "_dataset_id": "forged.dataset",
            "_request_sha256": "sha256:" + "0" * 64,
        }
        for name, value in forged_fields.items():
            with pytest.raises(AttributeError):
                object.__setattr__(permit, name, value)
        assert AppendOnlyEvidenceJournal._live_acquire_permits.get(permit) is issued
        return await original_acquire(
            pool,
            permit,
            connector_id=connector_id,
            dataset_id=dataset_id,
        )

    monkeypatch.setattr(
        ConnectionPool,
        "_acquire_with_live_permit",
        _attempt_mutation_then_acquire,
    )
    monkeypatch.setattr(WorldBankConnector, "health_check", _track_health_check)

    class _InterceptedResponse:
        status = 200
        headers: ClassVar[dict[str, str]] = {"content-type": "application/json"}

        async def __aenter__(self) -> _InterceptedResponse:
            return self

        async def __aexit__(self, *args: object) -> None:
            del args

        async def read(self) -> bytes:
            return body

        def release(self) -> None:
            return None

        async def wait_for_close(self) -> None:
            return None

        def close(self) -> None:
            return None

    async def _intercept_request(
        _session: object,
        method: str,
        url: object,
        **kwargs: object,
    ) -> _InterceptedResponse:
        params = kwargs.get("params")
        assert isinstance(params, Mapping)
        normalized = {str(key): str(value) for key, value in params.items()}
        transport_calls.append((method, str(url), normalized))
        return _InterceptedResponse()

    def _forbid_socket(*args: object, **kwargs: object) -> None:
        del args, kwargs
        pytest.fail("intercepted integration escaped to a real network socket")

    monkeypatch.setattr(aiohttp.ClientSession, "_request", _intercept_request)
    monkeypatch.setattr(socket.socket, "connect", _forbid_socket)
    monkeypatch.setattr(socket.socket, "connect_ex", _forbid_socket)

    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root).with_ambient_ownership_enforcement()
    with tenant_scope(None, tenant_id="tenant-wdi", cell_id="cell-wdi"):
        evidence = execute_live_catalog_acquisition(
            authority=authority,
            entry_id=entry.entry_id,
            attempt_id=_ATTEMPT_ID,
            constraints=_constraints(),
            journal_path=tmp_path / "journal.jsonl",
            cas_root=cas_root,
            artifact_store=store,
        )

    assert transport_calls == [("GET", _URL, _PARAMS)]
    assert scope_entries == [(_ATTEMPT_ID, _CONNECTOR_ID, _INDICATOR_ID)]
    assert len(scoped_permits) == len(pool_permits) == 1
    assert scoped_permits[0] is pool_permits[0]
    assert health_checks == []
    assert evidence.call_count == 1
    assert evidence.variable_count == 1
    assert evidence.transport_trace.raw_evidence_ref == evidence.raw_evidence_ref
    with tenant_scope(None, tenant_id="tenant-wdi", cell_id="cell-wdi"):
        reopened = authority.resolve_live_source_execution(
            entry.entry_id,
            evidence,
            store,
        )
        assert reopened.row_count == 2

    foreign_store = FileSystemCAS(cas_root).for_tenant("tenant-other", "cell-other")
    with tenant_scope(None, tenant_id="tenant-other", cell_id="cell-other"):
        with pytest.raises(ArtifactOwnershipError):
            foreign_store.get_bytes(evidence.raw_artifact_id)


def test_live_executor_recomputes_full_authorization_before_issuing_pool_permit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_builder = acquisition_executor_module.fabric_data_plane.build_live_execution_authorization
    calls = 0

    def _forge_first_authorization(**kwargs: Any):
        nonlocal calls
        authorization = original_builder(**kwargs)
        calls += 1
        if calls == 1:
            return authorization.model_copy(update={"baseline_sha256": "sha256:" + "0" * 64})
        return authorization

    monkeypatch.setattr(
        acquisition_executor_module.fabric_data_plane,
        "build_live_execution_authorization",
        _forge_first_authorization,
    )
    execute_calls = 0
    original_execute = acquisition_executor_module._execute_authorized_live_acquisition

    def _track_execute(**kwargs: Any):
        nonlocal execute_calls
        execute_calls += 1
        return original_execute(**kwargs)

    monkeypatch.setattr(
        acquisition_executor_module,
        "_execute_authorized_live_acquisition",
        _track_execute,
    )

    with pytest.raises(LiveAcquisitionExecutionError) as exc_info:
        _run(tmp_path, monkeypatch)

    assert exc_info.value.code == "live_acquire_authorization_mismatch"
    assert execute_calls == 0
    terminal = _failure_terminal(tmp_path / "journal.jsonl")
    assert terminal.failure_code == "live_acquire_authorization_mismatch"


def test_live_acquire_permit_rejects_a_reconstructed_copy_before_pool_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aiohttp

    from polisyos.fabric.connectors.pool import ConnectionPool

    authority, entry = _resolved_live_worldbank_authority(tmp_path)
    original_acquire = ConnectionPool._acquire_with_live_permit
    connection_creations: list[str] = []
    health_checks: list[str] = []
    transport_calls: list[tuple[str, str]] = []
    original_connect = WorldBankConnector.connect
    original_health_check = WorldBankConnector.health_check

    async def _acquire_with_clone(
        pool: ConnectionPool,
        permit: object,
        *,
        connector_id: str,
        dataset_id: str,
    ) -> Any:
        clone = object.__new__(type(permit))
        forged_issuer = SimpleNamespace(
            _consume_live_acquire_permit=lambda **_kwargs: None
        )
        forged_fields = {
            "_journal": forged_issuer,
            "_journal_path": "/tmp/forged-journal.jsonl",
            "_journal_sha256": "sha256:" + "0" * 64,
            "_request_ref": object(),
            "_attempt_id": "forged-attempt",
            "_connector_id": "forged.connector",
            "_dataset_id": "forged.dataset",
            "_request_sha256": "sha256:" + "0" * 64,
        }
        for name, value in forged_fields.items():
            with pytest.raises(AttributeError):
                object.__setattr__(clone, name, value)
        return await original_acquire(
            pool,
            clone,
            connector_id=connector_id,
            dataset_id=dataset_id,
        )

    async def _track_connect(self: WorldBankConnector, config: Any):
        connection_creations.append(_CONNECTOR_ID)
        return await original_connect(self, config)

    async def _track_health_check(self: WorldBankConnector, handle: object):
        health_checks.append(str(getattr(handle, "session_id", "unknown")))
        return await original_health_check(self, handle)

    async def _intercept_unexpected_request(
        _session: object,
        method: str,
        url: object,
        **kwargs: object,
    ) -> object:
        del kwargs
        transport_calls.append((method, str(url)))
        raise RuntimeError("reconstructed permit reached HTTP transport")

    def _forbid_socket(*args: object, **kwargs: object) -> None:
        del args, kwargs
        pytest.fail("reconstructed permit escaped to a real socket")

    monkeypatch.setattr(ConnectionPool, "_acquire_with_live_permit", _acquire_with_clone)
    monkeypatch.setattr(WorldBankConnector, "connect", _track_connect)
    monkeypatch.setattr(WorldBankConnector, "health_check", _track_health_check)
    monkeypatch.setattr(aiohttp.ClientSession, "_request", _intercept_unexpected_request)
    monkeypatch.setattr(socket.socket, "connect", _forbid_socket)
    monkeypatch.setattr(socket.socket, "connect_ex", _forbid_socket)

    with pytest.raises(LiveAcquisitionExecutionError) as exc_info:
        execute_live_catalog_acquisition(
            authority=authority,
            entry_id=entry.entry_id,
            attempt_id=_ATTEMPT_ID,
            constraints=_constraints(),
            journal_path=tmp_path / "journal.jsonl",
            cas_root=tmp_path / "cas",
            artifact_store=FileSystemCAS(tmp_path / "cas"),
        )

    assert exc_info.value.code == "live_acquire_permit_invalid"
    assert connection_creations == []
    assert health_checks == []
    assert transport_calls == []
    events = _journal_events(tmp_path / "journal.jsonl")
    request_events = [event for event in events if event["event_kind"] == "request"]
    assert len(request_events) == 1
    assert request_events[0]["attempt_id"] == _ATTEMPT_ID
    assert request_events[0]["request"]["request_dataset_id"] == _INDICATOR_ID
    assert all(event["event_kind"] != "transport_attempt" for event in events)


def test_live_acquire_permit_transition_is_atomic_across_threads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_execute = acquisition_executor_module._execute_authorized_live_acquisition
    results_seen: list[object] = []
    simultaneous_registry_reads: list[bool] = []

    def _contend_before_orchestration(**kwargs: Any):
        permit = kwargs["live_acquire_permit"]
        rendezvous = threading.Barrier(2)

        class _RendezvousRegistry(dict):
            def get(self, key: object, default: object = None) -> object:
                value = super().get(key, default)
                try:
                    rendezvous.wait(timeout=0.05)
                except threading.BrokenBarrierError:
                    simultaneous_registry_reads.append(False)
                else:
                    simultaneous_registry_reads.append(True)
                return value

        monkeypatch.setattr(
            AppendOnlyEvidenceJournal,
            "_live_acquire_permits",
            _RendezvousRegistry(AppendOnlyEvidenceJournal._live_acquire_permits),
        )
        start = threading.Barrier(2)

        def _consume() -> object:
            start.wait()
            try:
                _consume_live_acquire_permit(
                    permit,
                    connector_id=_CONNECTOR_ID,
                    dataset_id=_INDICATOR_ID,
                )
            except EvidenceJournalError as exc:
                return exc
            return None

        with ThreadPoolExecutor(max_workers=2) as executor:
            results_seen.extend(executor.map(lambda _index: _consume(), range(2)))
        return original_execute(**kwargs)

    monkeypatch.setattr(
        acquisition_executor_module,
        "_execute_authorized_live_acquisition",
        _contend_before_orchestration,
    )
    _authority, _evidence, stub, _journal_path = _run(tmp_path, monkeypatch)

    assert sum(result is None for result in results_seen) == 1
    failures = [result for result in results_seen if isinstance(result, EvidenceJournalError)]
    assert len(failures) == 1
    assert failures[0].code == "live_acquire_permit_invalid"
    assert simultaneous_registry_reads and not any(simultaneous_registry_reads)
    permit = stub.calls[0]["_live_acquire_permit"]
    with pytest.raises(EvidenceJournalError, match="live_acquire_permit_invalid"):
        _consume_live_acquire_permit(
            permit,
            connector_id=_CONNECTOR_ID,
            dataset_id=_INDICATOR_ID,
        )


def test_pool_rejects_concurrent_reuse_before_a_second_health_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aiohttp

    from polisyos.fabric.connectors.pool import ConnectionPool

    authority, entry = _resolved_live_worldbank_authority(tmp_path)
    body = _raw_body(_normalized_rows())
    transport_calls: list[tuple[str, str, dict[str, str]]] = []
    health_checks: list[str] = []
    original_acquire = ConnectionPool._acquire_with_live_permit
    attempted_permits: list[object] = []
    race_results: list[tuple[int, tuple[str, ...]]] = []
    original_health_check = WorldBankConnector.health_check

    class _InterceptedResponse:
        status = 200
        headers: ClassVar[dict[str, str]] = {"content-type": "application/json"}

        async def __aenter__(self) -> _InterceptedResponse:
            return self

        async def __aexit__(self, *args: object) -> None:
            del args

        async def read(self) -> bytes:
            return body

        def release(self) -> None:
            return None

        async def wait_for_close(self) -> None:
            return None

        def close(self) -> None:
            return None

    async def _race_same_permit(
        pool: ConnectionPool,
        permit: object,
        *,
        connector_id: str,
        dataset_id: str,
    ) -> Any:
        attempted_permits.append(permit)
        results = await asyncio.gather(
            original_acquire(
                pool,
                permit,
                connector_id=connector_id,
                dataset_id=dataset_id,
            ),
            original_acquire(
                pool,
                permit,
                connector_id=connector_id,
                dataset_id=dataset_id,
            ),
            return_exceptions=True,
        )
        acquired = [result for result in results if not isinstance(result, BaseException)]
        failures = tuple(
            str(getattr(result, "code", type(result).__name__))
            for result in results
            if isinstance(result, BaseException)
        )
        race_results.append((len(acquired), failures))
        assert len(acquired) == 1
        assert failures == ("live_acquire_permit_invalid",)
        result = acquired[0]
        assert isinstance(result, tuple)
        return result

    async def _track_health_check(self: WorldBankConnector, handle: object):
        health_checks.append(str(getattr(handle, "session_id", "unknown")))
        return await original_health_check(self, handle)

    async def _intercept_request(
        _session: object,
        method: str,
        url: object,
        **kwargs: object,
    ) -> _InterceptedResponse:
        params = kwargs.get("params")
        assert isinstance(params, Mapping)
        transport_calls.append(
            (method, str(url), {str(key): str(value) for key, value in params.items()})
        )
        return _InterceptedResponse()

    def _forbid_socket(*args: object, **kwargs: object) -> None:
        del args, kwargs
        pytest.fail("concurrent permit witness escaped to a real socket")

    monkeypatch.setattr(ConnectionPool, "_acquire_with_live_permit", _race_same_permit)
    monkeypatch.setattr(WorldBankConnector, "health_check", _track_health_check)
    monkeypatch.setattr(aiohttp.ClientSession, "_request", _intercept_request)
    monkeypatch.setattr(socket.socket, "connect", _forbid_socket)
    monkeypatch.setattr(socket.socket, "connect_ex", _forbid_socket)

    evidence = execute_live_catalog_acquisition(
        authority=authority,
        entry_id=entry.entry_id,
        attempt_id=_ATTEMPT_ID,
        constraints=_constraints(),
        journal_path=tmp_path / "journal.jsonl",
        cas_root=tmp_path / "cas",
        artifact_store=FileSystemCAS(tmp_path / "cas"),
    )

    assert evidence.call_count == 1
    assert race_results == [(1, ("live_acquire_permit_invalid",))]
    assert len(attempted_permits) == 1
    assert transport_calls == [("GET", _URL, _PARAMS)]
    assert health_checks == []
    with pytest.raises(EvidenceJournalError, match="live_acquire_permit_invalid"):
        _consume_live_acquire_permit(
            attempted_permits[0],
            connector_id=_CONNECTOR_ID,
            dataset_id=_INDICATOR_ID,
        )


def test_live_executor_blocks_out_of_authority_country_before_http_transport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aiohttp

    authority, entry = _resolved_live_worldbank_authority(tmp_path)
    scope_entries, _scoped_permits = _spy_on_journal_permit_scope(monkeypatch)
    transport_calls: list[tuple[str, str]] = []

    async def _intercept_unexpected_request(
        _session: object,
        method: str,
        url: object,
        **kwargs: object,
    ) -> object:
        del kwargs
        transport_calls.append((method, str(url)))
        raise RuntimeError("out-of-authority request reached the transport")

    def _forbid_socket(*args: object, **kwargs: object) -> None:
        del args, kwargs
        pytest.fail("out-of-authority probe escaped to a real socket")

    monkeypatch.setattr(aiohttp.ClientSession, "_request", _intercept_unexpected_request)
    monkeypatch.setattr(socket.socket, "connect", _forbid_socket)
    monkeypatch.setattr(socket.socket, "connect_ex", _forbid_socket)
    monkeypatch.setattr(
        WorldBankConnector,
        "_parse_countries",
        staticmethod(lambda _request: "POL"),
    )
    journal_path = tmp_path / "journal.jsonl"

    with pytest.raises(LiveAcquisitionExecutionError) as exc_info:
        execute_live_catalog_acquisition(
            authority=authority,
            entry_id=entry.entry_id,
            attempt_id=_ATTEMPT_ID,
            constraints=_constraints(),
            journal_path=journal_path,
            cas_root=tmp_path / "cas",
            artifact_store=FileSystemCAS(tmp_path / "cas"),
        )

    assert exc_info.value.code == "live_transport_request_drift"
    assert scope_entries == [(_ATTEMPT_ID, _CONNECTOR_ID, _INDICATOR_ID)]
    assert transport_calls == []
    events = _journal_events(journal_path)
    attempts = [event for event in events if event["event_kind"] == "transport_attempt"]
    assert len(attempts) == 1
    assert "/country/POL/" in attempts[0]["transport_attempt"]["url"]
    assert all(event["event_kind"] != "raw_response" for event in events)
