# Добавление источника данных

> Создайте новый Fabric source connector, зарегистрируйте reusable profile и подключите тесты и CI-проверки, которые делают коннектор production-safe.

## Перед началом

Сначала прочитайте [Connector CONTRIBUTING](../connectors/CONTRIBUTING.md).
Текущая connector-платформа уже содержит готовые production patterns для:

- HTTP/JSON источников
- SDMX API
- CKAN resources
- SPARQL endpoints

## 1. Выберите тип коннектора

Используйте актуальные class names и файлы из `src/polisyos/fabric/connectors/sources/`:

- Обычный REST или HTTP API:
  - наследуйтесь от `polisyos.fabric.connectors.sources.http_base.HTTPConnectorBase`
- SDMX-источник:
  - наследуйтесь от `polisyos.fabric.connectors.sources.sdmx_source.SDMXSourceConnector`
- CKAN resource endpoint:
  - наследуйтесь от `polisyos.fabric.connectors.sources.ckan_resource.CKANResourceConnector`
- SPARQL endpoint:
  - наследуйтесь от `polisyos.fabric.connectors.sources.sparql.SPARQLConnector`

Если ваш источник — это “ещё один HTTP API”, проще всего начать с `who.py` или `world_bank.py`.

## 2. Создайте класс коннектора

Новый файл размещайте под `src/polisyos/fabric/connectors/sources/`, например:

```python
# src/polisyos/fabric/connectors/sources/my_source.py
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, ClassVar

import pandas as pd

from polisyos.core.canon import streaming_hash
from polisyos.fabric.connectors.base import ConnectionHandle, FetchRequest, FetchResult, HealthStatus
from polisyos.fabric.connectors.sources.http_base import HTTPConnectorBase, HTTPResilienceProfile
from polisyos.fabric.connectors.types import DatasetDescriptor, FetchError
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
        | ConnectorCapability.DATE_RANGE_FILTER
        | ConnectorCapability.DIMENSION_FILTER
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
            ConnectorCapability.DATE_RANGE_FILTER,
            ConnectorCapability.DIMENSION_FILTER,
            ConnectorCapability.CATALOG_BROWSE,
            ConnectorCapability.SCHEMA_INTROSPECTION,
        ),
    )

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        started = time.monotonic()
        try:
            await self._resilient_request_json(handle, f"{self._base_url(handle)}/health")
            return HealthStatus(
                healthy=True,
                message="HTTP 200",
                latency_ms=self._elapsed_ms(started),
            )
        except Exception as exc:
            return HealthStatus(
                healthy=False,
                message=str(exc),
                latency_ms=self._elapsed_ms(started),
            )

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
        return {
            "schema_id": "my_source.generic",
            "dataset_id": dataset_id,
            "fields": ["field_a", "field_b"],
        }
```

Что полезно копировать из существующих простых коннекторов:

- `who.py`: чистый паттерн HTTP + нормализация в DataFrame
- `world_bank.py`: batched indicator fetch и более сильная metadata surface

## 3. Зарегистрируйте коннектор в `sources/__init__.py`

Добавьте и import, и имя в exported symbols:

```python
from polisyos.fabric.connectors.sources.my_source import MySourceConnector

__all__ = [
    # ...
    "MySourceConnector",
]
```

## 4. Создайте built-in source profile

Profiles находятся в `src/polisyos/fabric/connectors/profiles/`.
Добавьте запись в `builtin_profiles.py`:

```python
from .models import SourceProfile

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

### Какие поля `SourceProfile` обязательны?

Обязательные по текущей Pydantic-модели:

- `profile_id`
- `display_name`
- `connector_family`
- `base_url`

Поля, которые технически optional, но для production-коннектора очень желательны:

- `description`
- `auth_policy`
- `rate_limit_rps`
- `max_concurrency`
- `preferred_transport`
- `preferred_core_transport`
- `preferred_backfill_transport`
- `supports_async_fetch`
- `core_group_limit`
- `backfill_group_limit`
- `max_sync_cells`
- `max_async_cells`
- `capability_cache_ttl_hours`
- `negative_cache_ttl_hours`
- `soft_negative_cache_ttl_hours`
- `tags`
- `source_organization`
- `source_url`
- `estimated_datasets`

!!! note
    `SourceExecutionPolicy` автоматически вычисляется из profile через profile resolver.
    В обычном connector onboarding создавать `SourceExecutionPolicy` вручную не нужно.

## 5. Добавьте schema contract (опционально, но рекомендуется)

Если ваш коннектор возвращает стабильную форму данных, добавьте contract-файл в:

```text
src/polisyos/fabric/connectors/sources/_contracts/
```

Минимальный паттерн:

```python
# src/polisyos/fabric/connectors/sources/_contracts/my_source_contracts.py
from pydantic import BaseModel


class MySourceGenericSchema(BaseModel):
    schema_id: str = "my_source.generic"
    version: str = "1.0.0"
    fields: tuple[str, ...] = ("field_a", "field_b")
```

После этого возвращайте `schema_id` и `schema_version` из `fetch()` и `get_dataset_schema()`.

## 6. Протестируйте коннектор

В качестве шаблона используйте production-тесты коннекторов:

- `tests/fabric/connectors/sources/test_production_connectors.py`
- другие source-specific тесты под `tests/fabric/connectors/sources/`

Типичный unit-test паттерн локально:

```python
import asyncio

from polisyos.fabric.connectors.base import ConnectionConfig, FetchRequest
from polisyos.fabric.connectors.sources.my_source import MySourceConnector


def _run_async(coro):
    return asyncio.run(coro)


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

    result = _run_async(_exercise())
    assert result.row_count == 1
```

Integration-тесты против реального upstream API помечайте явно:

```python
import pytest


@pytest.mark.integration
def test_my_source_live_fetch():
    ...
```

## 7. Валидация в CI

Перед PR убедитесь, что коннектор проходит те же проверки, что и остальной репозиторий:

- connector tests под `tests/fabric/connectors/...`
- architecture и connector checks в `.github/workflows/ci.yml`
- schema / ABI-related checks в `.github/workflows/abi.yml`, если вы меняете публичные contracts

Связанные lint/CI-части:

- `.github/workflows/ci.yml`
- `tools/lint/lint_connector_hardening.py`
- `tools/lint/lint_connectors.py`

## Чеклист

- новый файл коннектора под `src/polisyos/fabric/connectors/sources/`
- import/export добавлен в `sources/__init__.py`
- built-in `SourceProfile` добавлен
- тесты добавлены в `tests/fabric/connectors/sources/`
- docs или schemas обновлены, если источник имеет стабильный публичный контракт

## Связанные документы

- [Connector CONTRIBUTING](../connectors/CONTRIBUTING.md)
- [Installation](install.md)
- [Deploy Runtime](deploy-runtime.md)
