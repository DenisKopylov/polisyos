"""
SPARQLConnector — SPARQL endpoint query connector.

Query-based connector with safety guardrails:
- dataset_id = query template name
- filters = template parameters
- Enforces LIMIT and timeout guardrails
- Supports Wikidata, DBpedia, and custom SPARQL endpoints

Config headers:
- X-SPARQL-DefaultGraph: default graph URI
- X-SPARQL-QueryTemplates: JSON mapping template_name → SPARQL query
"""

from __future__ import annotations

import json as _json
import re
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, ClassVar

import aiohttp
import pandas as pd

from polisyos.core.canon import content_hash as compute_content_hash
from polisyos.fabric.connectors.base import (
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.sources.http_base import (
    HTTPConnectorBase,
    HTTPResilienceProfile,
)
from polisyos.fabric.connectors.sources.http_common import frame_completeness
from polisyos.fabric.connectors.types import (
    DatasetDescriptor,
    FetchError,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from polisyos.fabric.safety import (
    UnsafeFilterExpressionError,
    escape_sparql_literal,
    validate_sparql_iri_token,
    validate_sparql_variable_name,
)
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    QualityTier,
    TrustLevel,
    capabilities_from_flags,
)

_MAX_LIMIT = 100000
_DEFAULT_TIMEOUT_HINT = 30  # seconds
_PLACEHOLDER_RE = re.compile(r"\{\{(?:(literal|iri|var):)?([A-Za-z_][A-Za-z0-9_]*)\}\}")


class SPARQLConnector(HTTPConnectorBase[pd.DataFrame]):
    """Connector for SPARQL endpoints such as Wikidata or DBpedia.

    Applies templated query execution, timeout guardrails, and endpoint-aware
    throttling before normalizing results into tabular frames.

    Data source:
        SPARQL-compatible knowledge graph endpoints
    Protocol:
        SPARQL over HTTP
    Auth:
        Usually none; profile-driven when needed
    Async support:
        Standard async HTTP execution only
    Profile:
        Any ``connector_family='sparql'`` profile
    """

    namespace: ClassVar[str] = "sparql"
    short_id: ClassVar[str] = "endpoint"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    _BASE_URL: ClassVar[str] = ""

    resilience_profile: ClassVar[HTTPResilienceProfile] = HTTPResilienceProfile(
        base_delay=2.0,
        max_delay=60.0,
        rate_limit_rps=2.0,
    )

    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH
        | ConnectorCapability.DIMENSION_FILTER
        | ConnectorCapability.RATE_LIMIT_AWARE
    )

    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace=namespace,
        source_name="SPARQL Endpoint",
        source_organization="Various linked data providers",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.BRONZE,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.DIMENSION_FILTER,
            ConnectorCapability.RATE_LIMIT_AWARE,
        ),
    )

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_query_templates(config: ConnectionConfig) -> dict[str, str]:
        raw = config.headers.get("X-SPARQL-QueryTemplates", "{}")
        try:
            templates = _json.loads(raw)
            if isinstance(templates, dict):
                return {str(k): str(v) for k, v in templates.items()}
        except _json.JSONDecodeError:
            pass
        return {}

    @staticmethod
    def _get_default_graph(config: ConnectionConfig) -> str | None:
        return config.headers.get("X-SPARQL-DefaultGraph") or None

    @staticmethod
    def _allow_inline_query(config: ConnectionConfig) -> bool:
        raw = config.headers.get("X-SPARQL-AllowInlineQuery", "")
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    # ------------------------------------------------------------------
    # Connect
    # ------------------------------------------------------------------

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        handle = await super().connect(config)
        handle.set_state("sparql_templates", self._get_query_templates(config))
        handle.set_state("sparql_default_graph", self._get_default_graph(config))
        return handle

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        base = self._base_url(handle)
        url = f"{base}/sparql" if not base.endswith("/sparql") else base
        started = time.monotonic()
        try:
            session = await self._get_session(handle)
            timeout = aiohttp.ClientTimeout(total=10)
            data = {"query": "ASK { ?s ?p ?o } LIMIT 1"}
            async with session.post(
                url,
                data=data,
                headers={"Accept": "application/sparql-results+json"},
                timeout=timeout,
            ) as resp:
                if resp.status < 400:
                    return HealthStatus(
                        healthy=True,
                        message="HTTP 200",
                        latency_ms=self._elapsed_ms(started),
                    )
                return HealthStatus(
                    healthy=False,
                    message=f"HTTP {resp.status}",
                    latency_ms=self._elapsed_ms(started),
                )
        except Exception as exc:
            return HealthStatus(
                healthy=False,
                message=str(exc),
                latency_ms=self._elapsed_ms(started),
            )

    # ------------------------------------------------------------------
    # Catalog browse (enumerate query templates)
    # ------------------------------------------------------------------

    async def list_datasets(
        self,
        handle: ConnectionHandle,
    ) -> AsyncIterator[DatasetDescriptor]:
        templates = handle.get_state("sparql_templates", {})
        for name, query in templates.items():
            yield DatasetDescriptor(
                dataset_id=name,
                name=name,
                description=query[:200],
                tags=("sparql",),
            )

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        base = self._base_url(handle)
        url = f"{base}/sparql" if not base.endswith("/sparql") else base

        query = self._resolve_query(handle, request)
        query = self._apply_guardrails(query)
        default_graph = handle.get_state("sparql_default_graph")

        started = time.monotonic()
        session = await self._get_session(handle)
        timeout = aiohttp.ClientTimeout(total=handle.config.timeout_seconds)

        data: dict[str, str] = {"query": query}
        if default_graph:
            data["default-graph-uri"] = default_graph

        async with session.post(
            url,
            data=data,
            headers={"Accept": "application/sparql-results+json"},
            timeout=timeout,
        ) as resp:
            headers = dict(resp.headers)
            if resp.status >= 400:
                raise FetchError(
                    message=f"SPARQL query returned HTTP {resp.status}",
                    connector_id=self.connector_id,
                    dataset_id=request.dataset_id,
                )
            raw = await resp.read()

        duration_ms = self._elapsed_ms(started)
        body = _json.loads(raw)
        df = self._parse_sparql_results(body)
        chash = compute_content_hash(raw, prefix=True)

        return self._build_fetch_result(
            data=df,
            row_count=len(df),
            schema_id=f"{self.connector_id}.{request.dataset_id}",
            schema_version="1.0.0",
            quality_tier=QualityTier.BRONZE,
            bytes_transferred=len(raw),
            completeness=frame_completeness(df) if not df.empty else 1.0,
            fetched_at=datetime.now(UTC),
            fetch_duration_ms=duration_ms,
            content_hash=chash,
            etag=headers.get("ETag"),
            last_modified=headers.get("Last-Modified"),
        )

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        return {
            "schema_id": f"{self.connector_id}.{dataset_id}",
            "version": "1.0.0",
            "format": "sparql-results",
            "notes": "Schema inferred from SPARQL query result columns.",
        }

    # ------------------------------------------------------------------
    # Query resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_query(handle: ConnectionHandle, request: FetchRequest) -> str:
        templates = handle.get_state("sparql_templates", {})
        query = templates.get(request.dataset_id)

        if query is None:
            if (
                handle.config.headers.get("X-SPARQL-AllowInlineQuery", "")
                and SPARQLConnector._allow_inline_query(handle.config)
                and request.dataset_id.strip()
                .upper()
                .startswith(("SELECT", "ASK", "CONSTRUCT", "DESCRIBE"))
            ):
                if request.filters:
                    raise UnsafeFilterExpressionError(
                        "Inline SPARQL queries do not support request-time filter substitution"
                    )
                query = request.dataset_id
            else:
                raise FetchError(
                    message=f"No SPARQL query template found for '{request.dataset_id}'",
                    connector_id="sparql.endpoint",
                    dataset_id=request.dataset_id,
                )

        filter_map = {str(key): tuple(values) for key, values in request.filters}
        placeholders = list(_PLACEHOLDER_RE.finditer(query))
        if not placeholders:
            if filter_map:
                unexpected = ", ".join(sorted(filter_map))
                raise UnsafeFilterExpressionError(
                    f"SPARQL template does not declare placeholders for filters: {unexpected}"
                )
            return query

        declared = {match.group(2) for match in placeholders}
        unexpected = sorted(set(filter_map) - declared)
        if unexpected:
            raise UnsafeFilterExpressionError(
                f"SPARQL template does not allow filters: {', '.join(unexpected)}"
            )

        missing = sorted(
            name for name in declared if name not in filter_map or not filter_map[name]
        )
        if missing:
            raise UnsafeFilterExpressionError(
                f"Missing SPARQL placeholder values: {', '.join(missing)}"
            )

        def _replace(match: re.Match[str]) -> str:
            kind = match.group(1)
            name = match.group(2)
            values = tuple(str(value) for value in filter_map.get(name, ()))
            if len(values) != 1:
                raise UnsafeFilterExpressionError(
                    f"SPARQL placeholder '{name}' expects exactly one value"
                )
            value = values[0]
            if kind == "literal":
                return escape_sparql_literal(value)
            if kind == "iri":
                return validate_sparql_iri_token(value, what=f"SPARQL placeholder '{name}'")
            if kind == "var":
                return validate_sparql_variable_name(
                    value,
                    what=f"SPARQL placeholder '{name}'",
                )
            raise UnsafeFilterExpressionError(
                f"SPARQL placeholder '{{{{{name}}}}}' must declare an explicit kind"
            )

        return _PLACEHOLDER_RE.sub(_replace, query)

    @staticmethod
    def _apply_guardrails(query: str) -> str:
        # Ensure LIMIT exists
        if not re.search(r"\bLIMIT\b", query, re.IGNORECASE):
            query = f"{query.rstrip()} LIMIT {_MAX_LIMIT}"
        else:
            # Ensure LIMIT is not too large
            match = re.search(r"\bLIMIT\s+(\d+)", query, re.IGNORECASE)
            if match:
                current_limit = int(match.group(1))
                if current_limit > _MAX_LIMIT:
                    query = re.sub(
                        r"\bLIMIT\s+\d+",
                        f"LIMIT {_MAX_LIMIT}",
                        query,
                        flags=re.IGNORECASE,
                    )
        return query

    # ------------------------------------------------------------------
    # Result parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_sparql_results(body: dict[str, Any]) -> pd.DataFrame:
        results = body.get("results", {})
        bindings = results.get("bindings", [])
        if not bindings:
            return pd.DataFrame()

        rows: list[dict[str, Any]] = []
        for binding in bindings:
            row: dict[str, Any] = {}
            for var_name, var_val in binding.items():
                row[var_name] = var_val.get("value", "")
            rows.append(row)

        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Validate config
    # ------------------------------------------------------------------

    @classmethod
    def validate_config(cls, config: ConnectionConfig) -> ValidationResult:
        issues: list[ValidationIssue] = []
        if not config.url:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="SPARQL endpoint URL is required",
                    field="url",
                )
            )
        if issues:
            return ValidationResult.failure(*issues)
        return ValidationResult.success()


__all__ = ["SPARQLConnector"]
