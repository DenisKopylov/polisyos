# Write Your First Connector

English edition: 2026-10-14 (translation only; not a source-freshness or execution claim).

Related how-to: [Add Data Source](../how-to/add-data-source.md). Related reference: [Fabric Connectors](../reference/fabric/connectors.md).

> This tutorial is for an engineer adding a data source to Fabric for the first
> time and who wants to follow the path from a new file through local validation.

!!! info "Historical review (2026-04-17)"
    The previous revision recorded a dry-run connector scaffold and imports of
    `WorldBankConnector` / `HTTPConnectorBase` in the environment used at that
    time. This is not a receipt that the full tutorial or its tests were run.
    Source paths were read at pin `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`;
    the production implementation under `src/polisyos/` has not changed since
    that pin. The examples and tests were not run for this documentation refresh.

This walkthrough does not cover every edge case in the connector platform. Its
goal is to assemble a minimal production-shaped connector, register it in the
public Fabric surface, and verify that it passes local checks.

If you need a skeleton before editing by hand, use the canonical connector CLI:

```bash
uv run polisyos-tools connectors scaffold create --name MySource --type REST --dry-run
```

## Step 1. Choose the right starting point

For most REST/JSON sources, start with:

- `polisyos.fabric.connectors.sources.http_base.HTTPConnectorBase`
- `polisyos.fabric.connectors.sources.http_base.HTTPResilienceProfile`

If the source resembles an existing family, use the closest production example:

- `WorldBankConnector` for an indicator-style API;
- `WHOConnector` for tabular HTTP responses;
- `SDMXSourceConnector` for an SDMX surface.

For new non-HTTP families, first open the capability contract in
`src/polisyos/fabric/connectors/family_contracts.py`.
It already provides scaffolds for:

- `files`
- `object_storage`
- `sql`
- `graphql`
- `geojson`
- `stream`

This is useful for two reasons:

- you can see the family's required capabilities and lineage requirements at
  once;
- the profile scaffold suggests the minimum `connector_family` / `base_url`.

## Step 2. Create a minimal connector class

Add a new file under `src/polisyos/fabric/connectors/sources/`, for example
`my_source.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, AsyncIterator, ClassVar

import pandas as pd

from polisyos.core.canon import streaming_hash
from polisyos.fabric.connectors.base import ConnectionHandle, FetchRequest, FetchResult, HealthStatus
from polisyos.fabric.connectors.sources.http_base import HTTPConnectorBase, HTTPResilienceProfile
from polisyos.fabric.connectors.types import DatasetDescriptor
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    QualityTier,
    TrustLevel,
    capabilities_from_flags,
)


class MySourceConnector(HTTPConnectorBase[pd.DataFrame]):
    namespace: ClassVar[str] = "my_source"
    short_id: ClassVar[str] = "public"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    _BASE_URL: ClassVar[str] = "https://api.example.com"
    resilience_profile: ClassVar[HTTPResilienceProfile] = HTTPResilienceProfile(base_delay=1.0)

    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH
        | ConnectorCapability.CATALOG_BROWSE
        | ConnectorCapability.SCHEMA_INTROSPECTION
    )

    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace=namespace,
        source_name="My Source",
        source_organization="Example Organization",
        source_url=_BASE_URL,
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.CATALOG_BROWSE,
            ConnectorCapability.SCHEMA_INTROSPECTION,
        ),
    )

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        await self._resilient_request_json(handle, f"{self._base_url(handle)}/health")
        return HealthStatus(healthy=True, message="HTTP 200", latency_ms=0.0)

    async def list_datasets(self, handle: ConnectionHandle) -> AsyncIterator[DatasetDescriptor]:
        body, _headers, _raw = await self._resilient_request_json(
            handle,
            f"{self._base_url(handle)}/datasets",
        )
        for row in body.get("items", []):
            yield DatasetDescriptor(
                dataset_id=str(row["id"]),
                name=str(row.get("name") or row["id"]),
                description=str(row.get("description") or ""),
                tags=("my_source",),
            )

    async def fetch(self, handle: ConnectionHandle, request: FetchRequest) -> FetchResult[pd.DataFrame]:
        body, headers, raw = await self._resilient_request_json(
            handle,
            f"{self._base_url(handle)}/datasets/{request.dataset_id}",
        )
        frame = pd.DataFrame(body["rows"])
        now = datetime.now(timezone.utc)
        return self._build_fetch_result(
            data=frame,
            row_count=len(frame),
            schema_id="my_source.generic",
            schema_version="1.0.0",
            quality_tier=QualityTier.SILVER,
            bytes_transferred=len(raw),
            completeness=1.0 if len(frame) else 0.0,
            fetched_at=now,
            fetch_duration_ms=0.0,
            content_hash=streaming_hash((raw,), prefix=True),
            etag=headers.get("ETag"),
            last_modified=headers.get("Last-Modified"),
        )

    async def get_dataset_schema(self, handle: ConnectionHandle, dataset_id: str) -> dict[str, Any]:
        del handle
        return {"schema_id": "my_source.generic", "dataset_id": dataset_id}
```

Important points:

- `connector_id` and metadata should be stable because profiles and control-plane
  discovery rely on them;
- `fetch()` should return the canonical `FetchResult`, not an arbitrary payload;
- set `schema_id` and `schema_version` early if the upstream shape is stable
  enough.

## Step 3. Export the connector in the public surface

Add the import and name in `src/polisyos/fabric/connectors/sources/__init__.py`:

```python
from polisyos.fabric.connectors.sources.my_source import MySourceConnector

__all__ = [
    # ...
    "MySourceConnector",
]
```

This matters for two reasons:

- the connector becomes part of Fabric's stable public surface;
- reference documentation and downstream tooling can discover it through the
  package facade.

## Step 4. Add a built-in profile

This step lets the control plane and profile resolver run the connector without
manually specifying a transport policy on every call.

Add the profile to `src/polisyos/fabric/connectors/profiles/builtin_profiles.py`:

```python
SourceProfile(
    profile_id="my_source_public",
    display_name="My Source Public API",
    description="Example public endpoint for My Source",
    connector_family="my_source",
    base_url="https://api.example.com",
    auth_policy="none",
    rate_limit_rps=5.0,
    max_concurrency=2,
    preferred_transport="default",
    preferred_core_transport="api_grouped",
    preferred_backfill_transport="api_grouped",
    supports_async_fetch=False,
    core_group_limit=100,
    backfill_group_limit=100,
    capability_cache_ttl_hours=24,
    negative_cache_ttl_hours=24,
    soft_negative_cache_ttl_hours=12,
    tags=["example", "public"],
    source_organization="Example Organization",
    source_url="https://example.com",
    estimated_datasets=100,
)
```

You usually do not need to construct `SourceExecutionPolicy` manually: it is
derived by the profile resolver on the runtime path.

### Family-first scaffold for new connector families

If you are adding a connector to a supported non-HTTP family rather than an
existing HTTP family, follow this order:

1. Define the family contract in `family_contracts.py` or reuse an existing one.
2. Check that connector metadata and hard capabilities actually cover
   `required_capabilities`.
3. Add at least one built-in profile scaffold in `builtin_profiles.py`, even if
   it is demo-oriented.
4. For schema introspection, decide up front which mode to use:

   - files/object storage: sample inference + format/provider metadata;
   - sql: query probe or information schema;
   - graphql: protocol query + sample inference;
   - geojson: feature properties + spatial metadata;
   - stream: message sample + stream metadata.
5. Put lineage metadata at the connector boundary from the start, rather than
   adding it as post-processing:

   - source location / bucket / object key
   - query or query document
   - CRS / geometry types
   - stream topic / message ids

## Step 5. Add at least one local test

The most useful first test for a new connector is a deterministic mock path, not
a live integration test.

```python
import asyncio

from polisyos.fabric.connectors.base import ConnectionConfig, FetchRequest
from polisyos.fabric.connectors.sources.my_source import MySourceConnector


def test_my_source_fetch_with_mock_http(monkeypatch) -> None:
    connector = MySourceConnector()

    async def _fake_request_json(_session, _url, *, params=None, connector_id=None):
        return {"rows": [{"field_a": 1, "field_b": 2}]}, {}, b'{"rows":[{"field_a":1,"field_b":2}]}'

    async def _fake_get_session(self, _handle):
        return object()

    monkeypatch.setattr(MySourceConnector, "_request_json", staticmethod(_fake_request_json))
    monkeypatch.setattr(MySourceConnector, "_get_session", _fake_get_session)

    async def _exercise():
        handle = await connector.connect(ConnectionConfig(url="https://example.test"))
        result = await connector.fetch(handle, FetchRequest(dataset_id="demo"))
        await connector.disconnect(handle)
        return result

    result = asyncio.run(_exercise())
    assert result.row_count == 1
```

After that, you can add a live test under `@pytest.mark.integration` if the
upstream is stable enough.

For WS-5B connector families, the minimum contract test should establish
family-specific acceptance as well as `fetch()`:

- files/object storage: format and source lineage are preserved;
- sql: query/table provenance and schema introspection are available;
- graphql: the query document and extracted data path are explainable;
- geojson: CRS and spatial metadata are preserved;
- stream: chunk/message IDs are deterministic and suitable for quarantine/replay.

## Step 6. Run local checks

Minimum local checks before a PR:

```bash
pytest tests/unit/fabric/connectors/sources -x --tb=short
uv run --extra docs python -m mkdocs build --strict
uv run --extra docs python tools/quality/validation/check_docstring_quality.py --repo-root . --allowlist tools/quality/validation/docstring_quality_allowlist.txt
```

If the public connector contract changed, also check the reference documentation
and schema-related pages.

## Next steps

- For a more complete checklist, see [Add Data Source](../how-to/add-data-source.md).
- For runtime/discovery scenarios, see [Use Control Plane](../how-to/use-control-plane.md).
- For Fabric contracts and surface, see the [Fabric Connectors reference](../reference/fabric/connectors.md).
