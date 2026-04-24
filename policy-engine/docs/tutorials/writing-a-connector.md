# Написание первого connector

Related how-to: [Add Data Source](../how-to/add-data-source.md). Related reference: [Fabric Connectors](../reference/fabric/connectors.md).

> Этот tutorial рассчитан на инженера, который впервые добавляет источник данных в Fabric и хочет пройти весь путь от нового файла до локальной валидации.

!!! info "Verified with"
Эта страница была перепроверена 2026-04-17 на текущем дереве, macOS,
Python 3.14 и `uv`.
Реально проверены
`uv run polisyos-tools connectors scaffold create --name MySource --type REST --dry-run`
и импорты `WorldBankConnector` / `HTTPConnectorBase`.

В walkthrough ниже мы не покрываем все edge cases connector platform. Цель другая: собрать минимальный production-shaped connector, зарегистрировать его в публичной поверхности Fabric и убедиться, что он проходит локальные проверки.

Если вам нужен skeleton до ручного редактирования, используйте canonical
connector CLI:

```bash
uv run polisyos-tools connectors scaffold create --name MySource --type REST --dry-run
```

## Шаг 1. Выберите правильную базу

Для большинства REST/JSON источников стартовая точка сегодня такая:

- `polisyos.fabric.connectors.sources.http_base.HTTPConnectorBase`
- `polisyos.fabric.connectors.sources.http_base.HTTPResilienceProfile`

Если источник уже похож на существующую семью, берите ближайший production пример:

- `WorldBankConnector` для indicator-style API
- `WHOConnector` для табличных HTTP ответов
- `SDMXSourceConnector` для SDMX surface

Для новых non-HTTP families сначала откройте capability contract в
`src/polisyos/fabric/connectors/family_contracts.py`.
Там уже есть scaffold для:

- `files`
- `object_storage`
- `sql`
- `graphql`
- `geojson`
- `stream`

Это полезно по двум причинам:

- вы сразу видите обязательные capabilities и lineage requirements для семьи;
- profile scaffold уже подсказывает минимальный `connector_family` / `base_url`.

## Шаг 2. Создайте минимальный connector class

Добавьте новый файл под `src/polisyos/fabric/connectors/sources/`, например `my_source.py`:

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

Что здесь важно:

- `connector_id` и metadata должны быть стабильными, потому что дальше на них опираются profiles и control-plane discovery;
- `fetch()` должен возвращать канонический `FetchResult`, а не произвольный payload;
- `schema_id` и `schema_version` лучше задавать сразу, если upstream shape достаточно стабилен.

## Шаг 3. Экспортируйте connector в публичную surface

Добавьте импорт и имя в `src/polisyos/fabric/connectors/sources/__init__.py`:

```python
from polisyos.fabric.connectors.sources.my_source import MySourceConnector

__all__ = [
    # ...
    "MySourceConnector",
]
```

Это важно по двум причинам:

- connector станет частью стабильной публичной surface Fabric;
- reference docs и downstream tooling увидят его через package facade.

## Шаг 4. Добавьте built-in profile

Следующий шаг нужен, чтобы control plane и profile resolver могли запускать connector без ручного описания transport policy на каждый вызов.

Добавьте профиль в `src/polisyos/fabric/connectors/profiles/builtin_profiles.py`:

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

`SourceExecutionPolicy` вручную собирать обычно не нужно: он выводится из profile resolver на runtime path.

### Family-first scaffold для новых connector families

Если вы добавляете коннектор не в существующую HTTP family, а в одну из новых WS-5B families, ориентируйтесь на такой порядок:

1. Определите family contract в `family_contracts.py` или переиспользуйте существующий.
2. Проверьте, что connector metadata и hard capabilities реально покрывают `required_capabilities`.
3. Добавьте хотя бы один built-in profile scaffold в `builtin_profiles.py`, даже если он demo-oriented.
4. Для schema introspection сразу решите, какой режим используете:

   - files/object storage: sample inference + format/provider metadata
   - sql: query probe или information schema
   - graphql: protocol query + sample inference
   - geojson: feature properties + spatial metadata
   - stream: message sample + stream metadata
5. Сразу положите lineage metadata в connector boundary, а не как post-processing:

   - source location / bucket / object key
   - query or query document
   - CRS / geometry types
   - stream topic / message ids

## Шаг 5. Добавьте хотя бы один локальный тест

Самый полезный первый тест для нового connector-а не live integration, а deterministic mock-path.

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

После этого можно добавить live test под `@pytest.mark.integration`, если upstream достаточно стабилен.

Для WS-5B connector families минимальный contract test должен доказывать не только `fetch()`, но и family-specific acceptance:

- files/object storage: формат и source lineage сохраняются;
- sql: query/table provenance и schema introspection доступны;
- graphql: query document и extracted data path объяснимы;
- geojson: CRS и spatial metadata не теряются;
- stream: chunk/message IDs детерминированы и пригодны для quarantine/replay.

## Шаг 6. Прогоните локальные проверки

Минимальный локальный набор перед PR:

```bash
pytest tests/fabric/connectors/sources -x --tb=short
uv run --extra docs python -m mkdocs build --strict
uv run --extra docs python tools/validation/check_docstring_quality.py --repo-root . --allowlist tools/validation/docstring_quality_allowlist.txt
```

Если менялся публичный connector contract, дополнительно проверьте reference docs и schema-related pages.

## Что дальше

- Для более полного checklist перейдите в [Add Data Source](../how-to/add-data-source.md)
- Для runtime/discovery сценариев посмотрите [Use Control Plane](../how-to/use-control-plane.md)
- Для контрактов и surface Fabric откройте [Fabric Connectors reference](../reference/fabric/connectors.md)
