"""Cache-first URL acquisition backed by CAS artifacts plus a JSON index."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.scholar.search.models import FetchResult

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.artifacts.protocol import ArtifactStore


class CachedPageRecord(BaseModel):
    """One cache index entry for fetched page text and metadata."""

    model_config = ConfigDict(extra="forbid")

    url: str
    final_url: str
    title: str = ""
    text: str = ""
    content_type: str = "application/octet-stream"
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: str = "ok"
    content_sha256: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    redirect_chain: list[str] = Field(default_factory=list)
    paywalled: bool = False
    error: str | None = None
    source_type: str = "web"
    artifact_id: str | None = None
    raw_artifact_ref: ArtifactRef | None = None
    byte_size: int | None = Field(default=None, ge=0)
    license: str = "public-web"
    fetch_profile: dict[str, Any] = Field(default_factory=dict)
    lineage_parent_artifact_id: str | None = None
    refresh_reason: str | None = None

    def to_fetch_result(self) -> FetchResult:
        return FetchResult.model_validate(
            {
                "url": self.url,
                "final_url": self.final_url,
                "title": self.title,
                "text": self.text,
                "content_type": self.content_type,
                "fetched_at": self.fetched_at,
                "status": cast(
                    "str",
                    "cached" if self.status == "ok" else self.status,
                ),
                "content_sha256": self.content_sha256,
                "etag": self.etag,
                "last_modified": self.last_modified,
                "redirect_chain": list(self.redirect_chain),
                "paywalled": self.paywalled,
                "error": self.error,
                "source_type": self.source_type,
                "artifact_id": self.artifact_id,
                "raw_artifact_ref": self.raw_artifact_ref,
                "byte_size": self.byte_size,
                "license": self.license,
                "fetch_profile": dict(self.fetch_profile),
                "lineage_parent_artifact_id": self.lineage_parent_artifact_id,
                "refresh_reason": self.refresh_reason,
            }
        )


class UrlFetchCache:
    """Persist fetched page metadata/text and reuse recent records before live fetch."""

    def __init__(
        self,
        *,
        index_path: Path | None = None,
        cas: ArtifactStore | None = None,
        ttl_seconds: int = 86_400,
    ) -> None:
        self._index_path = index_path
        self._cas = cas
        self._ttl_seconds = max(int(ttl_seconds), 0)
        self._records: dict[str, CachedPageRecord] = {}
        if index_path is not None and index_path.exists():
            try:
                payload = json.loads(index_path.read_text("utf-8"))
                if isinstance(payload, dict):
                    for url, item in payload.items():
                        if isinstance(url, str) and isinstance(item, dict):
                            self._records[url] = CachedPageRecord.model_validate(item)
            except Exception:
                self._records = {}

    def get(self, url: str) -> CachedPageRecord | None:
        record = self._records.get(url)
        if record is None:
            return None
        if self._ttl_seconds <= 0:
            return None
        age = datetime.now(UTC) - record.fetched_at
        if age.total_seconds() > self._ttl_seconds:
            return None
        return record

    def put(self, result: FetchResult, *, raw_bytes: bytes | None = None) -> CachedPageRecord:
        artifact_id = result.artifact_id
        raw_artifact_ref = result.raw_artifact_ref
        if raw_artifact_ref is not None:
            ref_artifact_id = str(raw_artifact_ref.artifact_id)
            if artifact_id is not None and artifact_id != ref_artifact_id:
                raise ValueError("FetchResult artifact_id must match raw_artifact_ref")
            artifact_id = ref_artifact_id
        previous = self._records.get(str(result.url))
        if self._cas is not None and raw_bytes is not None:
            ref = self._cas.put_bytes(
                raw_bytes,
                ArtifactWriteOptions(
                    kind="scholar.web_fetch_payload",
                    media_type=result.content_type,
                    schema=SchemaInfo(name="polisyos.scholar.web_fetch_payload", version="1.0"),
                    producer=ProducerInfo(
                        component="polisyos.scholar.search.cache", version="1.0.0"
                    ),
                ),
            )
            artifact_id = str(ref.artifact_id)
            raw_artifact_ref = ref

        if (
            artifact_id is not None
            and previous is not None
            and previous.artifact_id is not None
            and previous.artifact_id != artifact_id
            and result.lineage_parent_artifact_id is None
        ):
            result.lineage_parent_artifact_id = previous.artifact_id
            if result.refresh_reason is None:
                result.refresh_reason = "cache-refresh"
        if raw_bytes is not None:
            result.byte_size = len(raw_bytes)
        result.artifact_id = artifact_id
        result.raw_artifact_ref = raw_artifact_ref

        record = CachedPageRecord(
            url=str(result.url),
            final_url=result.final_url,
            title=result.title,
            text=result.text,
            content_type=result.content_type,
            fetched_at=result.fetched_at,
            status="ok" if result.status == "cached" else result.status,
            content_sha256=result.content_sha256,
            etag=result.etag,
            last_modified=result.last_modified,
            redirect_chain=list(result.redirect_chain),
            paywalled=result.paywalled,
            error=result.error,
            source_type=result.source_type,
            artifact_id=artifact_id,
            raw_artifact_ref=raw_artifact_ref,
            byte_size=result.byte_size,
            license=result.license,
            fetch_profile=dict(result.fetch_profile),
            lineage_parent_artifact_id=result.lineage_parent_artifact_id,
            refresh_reason=result.refresh_reason,
        )
        self._records[str(result.url)] = record
        self._flush()
        return record

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {
            url: record.model_dump(mode="json", exclude_none=True)
            for url, record in sorted(self._records.items())
        }

    def _flush(self) -> None:
        if self._index_path is None:
            return
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._index_path.with_suffix(self._index_path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(self.snapshot(), sort_keys=True, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self._index_path)


__all__ = [
    "CachedPageRecord",
    "UrlFetchCache",
]
