"""Shared helpers for file-like connector families."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
import pandas as pd

from polisyos.core.canon import content_hash
from polisyos.fabric.connectors.contracts import infer_schema
from polisyos.ir.connectors import DataVersion, VersionStrategy


def _strip_internal_headers(
    headers: dict[str, str], *, prefixes: tuple[str, ...]
) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if not any(key.startswith(prefix) for prefix in prefixes)
    }


def infer_file_format(location: str, explicit_format: str | None = None) -> str:
    """Infer file format from explicit config or location suffix."""

    if explicit_format:
        return explicit_format.strip().lower()

    path = urlparse(location).path or location
    suffix = Path(path).suffix.lower()
    if suffix in {".csv"}:
        return "csv"
    if suffix in {".jsonl", ".ndjson"}:
        return "jsonl"
    if suffix in {".parquet"}:
        return "parquet"
    if suffix in {".xls", ".xlsx"}:
        return "excel"
    if suffix in {".geojson", ".json"}:
        return "geojson" if suffix == ".geojson" else "jsonl"
    raise ValueError(f"Could not infer dataset format from location {location!r}")


def parse_file_config(config) -> dict[str, str]:
    headers = dict(config.headers)
    return {
        "format": headers.get("X-File-Format", ""),
        "encoding": headers.get("X-File-Encoding", "utf-8"),
        "delimiter": headers.get("X-File-Delimiter", ","),
        "sheet_name": headers.get("X-File-Sheet", "0"),
    }


async def read_location_bytes(
    config, *, prefixes: tuple[str, ...] = ("X-File-",)
) -> tuple[bytes, dict[str, str]]:
    """Read bytes from file/http(s) locations without eager heavy imports."""

    url = str(config.url)
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme in {"", "file"}:
        path = Path(parsed.path if scheme == "file" else url)
        return path.read_bytes(), {
            "Last-Modified": datetime.fromtimestamp(
                path.stat().st_mtime,
                tz=UTC,
            ).isoformat(),
        }
    if scheme in {"s3", "gs", "gcs", "az", "azure", "abfs", "adl"}:
        try:
            import fsspec
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                f"Reading {scheme}:// locations requires optional dependency 'fsspec'"
            ) from exc

        with fsspec.open(url, "rb") as handle:
            data = handle.read()

        headers: dict[str, str] = {}
        try:
            fs, _token, paths = fsspec.get_fs_token_paths(url)
            info = fs.info(paths[0])
            etag = info.get("etag") or info.get("ETag")
            modified = (
                info.get("LastModified")
                or info.get("last_modified")
                or info.get("mtime")
                or info.get("updated")
            )
            if etag:
                headers["ETag"] = str(etag)
            if modified:
                headers["Last-Modified"] = str(modified)
        except Exception:
            headers = {}
        return data, headers

    transport_headers = _strip_internal_headers(dict(config.headers), prefixes=prefixes)
    timeout = aiohttp.ClientTimeout(total=config.timeout_seconds)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=transport_headers) as response:
            response.raise_for_status()
            return await response.read(), dict(response.headers)


def dataframe_from_bytes(
    data: bytes,
    *,
    location: str,
    format_name: str,
    encoding: str = "utf-8",
    delimiter: str = ",",
    sheet_name: str = "0",
) -> pd.DataFrame:
    """Parse supported tabular formats into a DataFrame."""

    fmt = infer_file_format(location, format_name)
    if fmt == "csv":
        return pd.read_csv(io.BytesIO(data), encoding=encoding, delimiter=delimiter)
    if fmt == "jsonl":
        return pd.read_json(io.BytesIO(data), lines=True)
    if fmt == "parquet":
        return pd.read_parquet(io.BytesIO(data))
    if fmt == "excel":
        parsed_sheet: int | str = int(sheet_name) if str(sheet_name).isdigit() else sheet_name
        return pd.read_excel(io.BytesIO(data), sheet_name=parsed_sheet)
    raise ValueError(f"unsupported file format {fmt!r}")


def schema_dict_from_dataframe(
    dataframe: pd.DataFrame,
    *,
    schema_id: str,
    extras: dict[str, object] | None = None,
) -> dict[str, object]:
    schema = infer_schema(dataframe, schema_id=schema_id)
    payload: dict[str, object] = {
        "schema_id": schema.schema_id,
        "version": str(schema.version),
        "fields": [
            {
                "name": field.name,
                "data_type": field.data_type.value,
                "nullable": field.nullable,
                "semantic_type": field.semantic_type.value if field.semantic_type else None,
            }
            for field in schema.fields
        ],
    }
    if extras:
        payload.update(extras)
    return payload


def content_version(
    *,
    data: bytes,
    etag: str | None = None,
    last_modified: str | None = None,
) -> DataVersion:
    """Build a version envelope preferring transport-native version hints."""

    now = datetime.now(UTC)
    digest = "sha256:" + content_hash(data)
    if etag:
        return DataVersion(
            strategy=VersionStrategy.ETAG,
            value=etag,
            timestamp=now,
            content_hash=digest,
        )
    if last_modified:
        return DataVersion(
            strategy=VersionStrategy.TIMESTAMP,
            value=last_modified,
            timestamp=now,
            content_hash=digest,
        )
    return DataVersion(
        strategy=VersionStrategy.CONTENT_HASH,
        value=digest,
        timestamp=now,
        content_hash=digest,
    )


__all__ = [
    "content_version",
    "dataframe_from_bytes",
    "infer_file_format",
    "parse_file_config",
    "read_location_bytes",
    "schema_dict_from_dataframe",
]
