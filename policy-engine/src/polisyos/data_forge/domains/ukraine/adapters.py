"""Source adapter protocol and generic tabular adapter implementations."""

from __future__ import annotations

import gzip
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from zipfile import ZipFile

import pandas as pd

from polisyos.data_forge.domains.ukraine.manifests import (
    ArtifactRecord,
    NormalizedArtifactManifest,
    SkippedSourceManifest,
    SourceSnapshotManifest,
    ValidationFinding,
    utc_now_iso,
    write_manifest,
)
from polisyos.data_forge.domains.ukraine.models import BuildRootConfig, SourceConfig, StageId
from polisyos.data_forge.kernel.io import ensure_dirs

_UKRAINE_OBLAST_CODE_MAP = {
    "вінницька": "05",
    "волинська": "07",
    "дніпропетровська": "12",
    "донецька": "14",
    "житомирська": "18",
    "закарпатська": "21",
    "запорізька": "23",
    "івано-франківська": "26",
    "київська": "32",
    "кіровоградська": "35",
    "луганська": "44",
    "львівська": "46",
    "миколаївська": "48",
    "одеська": "51",
    "полтавська": "53",
    "рівненська": "56",
    "сумська": "59",
    "тернопільська": "61",
    "харківська": "63",
    "херсонська": "65",
    "хмельницька": "68",
    "черкаська": "71",
    "чернівецька": "73",
    "чернігівська": "74",
    "м. київ": "80",
    "київ": "80",
    "севастополь": "85",
    "автономна республіка крим": "01",
    "крим": "01",
}


@dataclass(frozen=True)
class SourceExecutionContext:
    """Shared filesystem context used by source adapters."""

    build_root: BuildRootConfig

    def raw_dir(self, source_id: str) -> Path:
        return self.build_root.raw_dir / source_id

    def normalized_dir(self, source_id: str) -> Path:
        return self.build_root.normalized_dir / source_id

    def manifest_dir(self, source_id: str) -> Path:
        return self.build_root.manifests_dir / source_id


class SourceAdapter(Protocol):
    """Protocol implemented by all Ukraine data source adapters."""

    adapter_id: str

    def discover(self, source: SourceConfig, ctx: SourceExecutionContext) -> list[str]:
        """Return raw source locations that should be fetched."""

    def fetch(
        self,
        source: SourceConfig,
        ctx: SourceExecutionContext,
    ) -> SourceSnapshotManifest | SkippedSourceManifest:
        """Materialize raw artifacts and emit a source snapshot manifest."""

    def normalize(
        self,
        source: SourceConfig,
        snapshot: SourceSnapshotManifest,
        ctx: SourceExecutionContext,
        *,
        identity_resolver: AgentIdentityResolver | None = None,
    ) -> NormalizedArtifactManifest:
        """Produce the normalized parquet output for one source."""

    def validate(
        self,
        source: SourceConfig,
        manifest: NormalizedArtifactManifest,
    ) -> list[ValidationFinding]:
        """Validate one normalized artifact manifest."""


class AgentIdentityResolver:
    """Resolve missing ``agent_id`` values using registry identity columns."""

    def __init__(self, registry_frame: pd.DataFrame) -> None:
        self._registry_frame = registry_frame.copy()
        self._lookup: dict[str, dict[str, str]] = {}
        for key in ("agent_id", "registration_code", "tax_id", "edrpou"):
            if key in self._registry_frame.columns:
                pairs = self._registry_frame[[key, "agent_id"]].dropna()
                self._lookup[key] = {
                    self._normalize_identity(source): str(agent_id)
                    for source, agent_id in pairs.itertuples(index=False)
                }

    @staticmethod
    def _normalize_identity(value: object) -> str:
        text = str(value).strip().lower()
        return "".join(ch for ch in text if ch.isalnum())

    def attach(self, frame: pd.DataFrame, *, candidate_columns: list[str]) -> pd.DataFrame:
        """Fill ``agent_id`` where possible using configured identity columns."""

        result = frame.copy()
        if "agent_id" not in result.columns:
            result["agent_id"] = None
        unresolved = result["agent_id"].isna()
        for column in candidate_columns:
            if column not in result.columns:
                continue
            lookup = self._lookup.get(column) or self._lookup.get("registration_code")
            if not lookup:
                continue
            lookup_map = lookup
            mapped = result.loc[unresolved, column].map(
                lambda value, lookup_map=lookup_map: lookup_map.get(self._normalize_identity(value))
            )
            result.loc[unresolved, "agent_id"] = mapped
            unresolved = result["agent_id"].isna()
            if not unresolved.any():
                break
        return result


class TabularSourceAdapter:
    """Generic adapter for local files or HTTP URLs containing tabular data."""

    adapter_id = "tabular"

    def discover(self, source: SourceConfig, ctx: SourceExecutionContext) -> list[str]:
        del ctx
        if source.local_path is not None:
            return [str(source.local_path)]
        if source.endpoint is not None:
            return [source.endpoint]
        if source.required:
            raise FileNotFoundError(
                f"Source {source.source_id} requires either local_path or endpoint"
            )
        return []

    def fetch(
        self,
        source: SourceConfig,
        ctx: SourceExecutionContext,
    ) -> SourceSnapshotManifest | SkippedSourceManifest:
        locations = self.discover(source, ctx)
        if not locations and not source.required:
            manifest = SkippedSourceManifest(
                source_id=source.source_id,
                reason=source.optional_reason or "optional_source_not_configured",
                skipped_at=utc_now_iso(),
            )
            write_manifest(
                ctx.manifest_dir(source.source_id) / "skipped_source_manifest.json", manifest
            )
            return manifest

        raw_dir = ctx.raw_dir(source.source_id)
        ensure_dirs(raw_dir, ctx.manifest_dir(source.source_id))
        raw_artifacts: list[ArtifactRecord] = []
        for location in locations:
            if location.startswith("http://") or location.startswith("https://"):
                destination = raw_dir / Path(location).name
                urllib.request.urlretrieve(location, destination)  # noqa: S310
            else:
                source_path = Path(location)
                if not source_path.exists():
                    raise FileNotFoundError(f"Source input does not exist: {source_path}")
                destination = raw_dir / source_path.name
                resolved_source = source_path.resolve()
                resolved_raw_root = ctx.build_root.raw_dir.resolve()
                if resolved_source == raw_dir.resolve() or resolved_source.is_relative_to(
                    resolved_raw_root
                ):
                    destination = source_path
                if source_path.is_dir():
                    if source_path.resolve() != destination.resolve():
                        shutil.copytree(source_path, destination, dirs_exist_ok=True)
                    else:
                        destination = source_path
                elif source_path.resolve() != destination.resolve():
                    shutil.copy2(source_path, destination)
            raw_artifacts.append(ArtifactRecord.from_path(destination))

        manifest = SourceSnapshotManifest(
            source_id=source.source_id,
            adapter_id=self.adapter_id,
            status="fetched",
            discovered_at=utc_now_iso(),
            raw_artifacts=raw_artifacts,
            endpoint=source.endpoint,
        )
        write_manifest(
            ctx.manifest_dir(source.source_id) / "source_snapshot_manifest.json", manifest
        )
        return manifest

    def normalize(
        self,
        source: SourceConfig,
        snapshot: SourceSnapshotManifest,
        ctx: SourceExecutionContext,
        *,
        identity_resolver: AgentIdentityResolver | None = None,
    ) -> NormalizedArtifactManifest:
        if not snapshot.raw_artifacts:
            raise ValueError(f"Source snapshot for {source.source_id} has no raw artifacts")
        raw_path = Path(snapshot.raw_artifacts[0].path)
        if raw_path.is_dir() and source.source_id == "spending_full":
            return self._normalize_spending_full_manifest(source, snapshot, ctx)
        frame, findings = self._normalize_special_source(source, raw_path)
        if frame is None:
            frame = self._read_frame(raw_path, source.raw_format)
            findings = []
        if source.column_map:
            frame = frame.rename(columns=source.column_map)
        if identity_resolver is not None and source.identity_columns:
            frame = identity_resolver.attach(frame, candidate_columns=source.identity_columns)
        frame = self._ensure_standard_columns(frame, source, snapshot)
        missing = [column for column in source.required_columns if column not in frame.columns]
        if missing:
            raise ValueError(f"Missing required columns for {source.source_id}: {missing}")

        destination_dir = ctx.normalized_dir(source.source_id)
        ensure_dirs(destination_dir)
        destination = destination_dir / source.normalized_artifact
        frame.to_parquet(destination, index=False)
        manifest = NormalizedArtifactManifest(
            source_id=source.source_id,
            stage_id=source.stage_id,
            status="normalized",
            normalized_artifact=ArtifactRecord.from_path(destination, row_count=len(frame)),
            schema_version="1.0",
            join_keys=[
                key
                for key in ("agent_id", "cell_id", "region_code", "sector_id", "period_id")
                if key in frame.columns
            ],
            lineage_fields=["source_snapshot_id", "schema_version", "record_hash"],
            findings=findings,
        )
        write_manifest(ctx.manifest_dir(source.source_id) / source.manifest_name, manifest)
        return manifest

    def _normalize_spending_full_manifest(
        self,
        source: SourceConfig,
        snapshot: SourceSnapshotManifest,
        ctx: SourceExecutionContext,
    ) -> NormalizedArtifactManifest:
        import duckdb

        raw_path = Path(snapshot.raw_artifacts[0].path)
        findings: list[ValidationFinding] = []
        sample_paths = sorted(raw_path.glob("transactions_sample_*.json"))
        daily_paths = sorted(raw_path.glob("daily/**/*.json.gz"))
        if daily_paths:
            sample_paths = []
        file_limit = self._seed_limit("POLISYOS_UKRAINE_DATA_SPENDING_FILE_LIMIT")
        selected_daily_paths = self._evenly_spaced_paths(daily_paths, file_limit)
        if file_limit is not None and daily_paths and len(selected_daily_paths) < len(daily_paths):
            findings.append(
                ValidationFinding(
                    severity="warning",
                    code="capped_spending_files",
                    message=f"Normalization sampled {len(selected_daily_paths)} of {len(daily_paths)} daily Spending files due configured cap.",
                )
            )

        chunk_dir = ctx.build_root.tmp_dir / source.source_id / "spending_chunks"
        if chunk_dir.exists():
            shutil.rmtree(chunk_dir)
        ensure_dirs(chunk_dir, ctx.normalized_dir(source.source_id))
        chunk_paths: list[Path] = []
        chunk_frames: list[pd.DataFrame] = []
        chunk_file_budget = self._coerce_positive_int(
            os.getenv("POLISYOS_UKRAINE_DATA_SPENDING_CHUNK_FILES"),
            default=4,
        )

        def flush_chunk() -> None:
            if not chunk_frames:
                return
            chunk_path = chunk_dir / f"chunk_{len(chunk_paths):06d}.parquet"
            pd.concat(chunk_frames, ignore_index=True).to_parquet(chunk_path, index=False)
            chunk_paths.append(chunk_path)
            chunk_frames.clear()

        for index, path in enumerate([*sample_paths, *selected_daily_paths], start=1):
            data = self._load_json_payload(path)
            if not isinstance(data, list):
                continue
            rows = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                source_agent_id = str(
                    item.get("payer_edrpou") or item.get("payer_edrpou_fact") or ""
                ).strip()
                target_agent_id = str(
                    item.get("recipt_edrpou") or item.get("recipt_edrpou_fact") or ""
                ).strip()
                if not source_agent_id or not target_agent_id:
                    continue
                rows.append(
                    {
                        "source_agent_id": source_agent_id,
                        "target_agent_id": target_agent_id,
                        "amount": self._coerce_float(item.get("amount") or item.get("amount_cop")),
                        "period_id": self._coerce_period_id(
                            item.get("trans_date") or item.get("doc_date")
                        ),
                        "registration_code": source_agent_id,
                    }
                )
            if not rows:
                continue
            chunk_frames.append(pd.DataFrame.from_records(rows))
            if len(chunk_frames) >= chunk_file_budget:
                flush_chunk()
            if index % 32 == 0:
                pass
        flush_chunk()

        destination_dir = ctx.normalized_dir(source.source_id)
        ensure_dirs(destination_dir)
        destination = destination_dir / source.normalized_artifact
        if destination.exists():
            destination.unlink()
        if not chunk_paths:
            empty_frame = pd.DataFrame(
                columns=[
                    "source_agent_id",
                    "target_agent_id",
                    "amount",
                    "period_id",
                    "registration_code",
                    "source_snapshot_id",
                    "schema_version",
                    "record_hash",
                ]
            )
            empty_frame.to_parquet(destination, index=False)
            manifest = NormalizedArtifactManifest(
                source_id=source.source_id,
                stage_id=source.stage_id,
                status="normalized",
                normalized_artifact=ArtifactRecord.from_path(destination, row_count=0),
                schema_version="1.0",
                join_keys=["period_id"],
                lineage_fields=["source_snapshot_id", "schema_version", "record_hash"],
                findings=findings,
            )
            write_manifest(ctx.manifest_dir(source.source_id) / source.manifest_name, manifest)
            return manifest

        con = duckdb.connect()
        chunk_glob = str(chunk_dir / "*.parquet").replace("'", "''")
        destination_sql = str(destination).replace("'", "''")
        snapshot_id = str(snapshot.raw_artifacts[0].sha256).replace("'", "''")
        con.execute(
            f"""
            create or replace temp table spending_agg as
            select
              source_agent_id,
              target_agent_id,
              sum(amount) as amount,
              period_id,
              min(registration_code) as registration_code
            from read_parquet('{chunk_glob}')
            group by 1, 2, 4
            """
        )
        row_count = int(con.execute("select count(*) from spending_agg").fetchone()[0])
        con.execute(
            f"""
            copy (
              select
                source_agent_id,
                target_agent_id,
                amount,
                period_id,
                registration_code,
                '{snapshot_id}' as source_snapshot_id,
                '1.0' as schema_version,
                md5(
                  coalesce(source_agent_id, '')
                  || '|'
                  || coalesce(target_agent_id, '')
                  || '|'
                  || coalesce(period_id, '')
                  || '|'
                  || cast(amount as varchar)
                ) as record_hash
              from spending_agg
            ) to '{destination_sql}' (format parquet, compression zstd)
            """
        )
        con.close()

        manifest = NormalizedArtifactManifest(
            source_id=source.source_id,
            stage_id=source.stage_id,
            status="normalized",
            normalized_artifact=ArtifactRecord.from_path(destination, row_count=row_count),
            schema_version="1.0",
            join_keys=["period_id"],
            lineage_fields=["source_snapshot_id", "schema_version", "record_hash"],
            findings=findings,
        )
        write_manifest(ctx.manifest_dir(source.source_id) / source.manifest_name, manifest)
        return manifest

    def validate(
        self,
        source: SourceConfig,
        manifest: NormalizedArtifactManifest,
    ) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        if not manifest.normalized_artifact.sha256:
            findings.append(
                ValidationFinding(
                    severity="error",
                    code="missing_sha256",
                    message=f"{source.source_id} normalized artifact is missing a SHA256 hash",
                )
            )
        if (
            manifest.normalized_artifact.row_count is not None
            and manifest.normalized_artifact.row_count <= 0
        ):
            findings.append(
                ValidationFinding(
                    severity="error",
                    code="empty_normalized_artifact",
                    message=f"{source.source_id} normalized artifact has no rows",
                )
            )
        return findings

    def _read_frame(self, path: Path, raw_format: str) -> pd.DataFrame:
        fmt = raw_format.lower()
        if fmt == "parquet" or path.suffix.lower() == ".parquet":
            return pd.read_parquet(path)
        if fmt == "csv" or path.suffix.lower() == ".csv":
            return pd.read_csv(path)
        if fmt == "json" or path.suffix.lower() == ".json":
            return pd.read_json(path)
        if fmt == "jsonl":
            return pd.read_json(path, lines=True)
        if fmt in {"xlsx", "xls"}:
            return pd.read_excel(path)
        raise ValueError(f"Unsupported raw format: {raw_format}")

    def _normalize_special_source(
        self,
        source: SourceConfig,
        raw_path: Path,
    ) -> tuple[pd.DataFrame | None, list[ValidationFinding]]:
        if not raw_path.is_dir():
            return None, []
        handlers = {
            "edr_current": self._normalize_edr_current,
            "spending_full": self._normalize_spending_full,
            "spending_contracts_procurement_proxy": self._normalize_spending_contracts_procurement_proxy,
            "prozorro_full": self._normalize_prozorro_full,
            "macro_nbu_derzhstat": self._normalize_macro_panel,
            "dps_financials": self._normalize_dps_financials,
            "household_microdata": self._normalize_household_microdata,
            "labor_force_microdata": self._normalize_labor_force_microdata,
            "pfu_debt": self._normalize_pfu_debt,
            "wage_arrears": self._normalize_wage_arrears,
            "distress_events": self._normalize_distress_events,
            "logistics_mobility_displacement": self._normalize_logistics_mobility_displacement,
            "land_cadastre": self._normalize_land_cadastre,
        }
        handler = handlers.get(source.source_id)
        if handler is None:
            return None, []
        return handler(raw_path)

    def _normalize_edr_current(
        self, raw_path: Path
    ) -> tuple[pd.DataFrame, list[ValidationFinding]]:
        rows: list[tuple[str, str, str, str, str]] = []
        findings: list[ValidationFinding] = []
        zip_names = ["UO.zip", "FOP.zip"]

        for zip_name in zip_names:
            archive_path = raw_path / zip_name
            if not archive_path.exists():
                findings.append(
                    ValidationFinding(
                        severity="warning",
                        code="missing_edr_archive",
                        message=f"Expected EDR archive is missing: {zip_name}",
                    )
                )
                continue
            with ZipFile(archive_path) as archive:
                xml_members = [name for name in archive.namelist() if name.lower().endswith(".xml")]
                if not xml_members:
                    continue
                with archive.open(xml_members[0]) as handle:
                    for _, elem in ET.iterparse(handle, events=("end",)):
                        if elem.tag != "SUBJECT":
                            continue
                        registration_code = self._edr_registration_code(elem, zip_name=zip_name)
                        if registration_code:
                            rows.append(
                                (
                                    f"agent::{self._stable_token(registration_code)}",
                                    registration_code,
                                    self._region_from_registration(
                                        self._xml_child_text(elem, "REGISTRATION")
                                    ),
                                    (
                                        self._xml_child_text(elem, "OPF")
                                        or ("FOP" if "FOP" in zip_name else "unknown")
                                    ).strip(),
                                    (self._xml_child_text(elem, "NAME") or "").strip(),
                                )
                            )
                        elem.clear()
        frame = pd.DataFrame(
            rows,
            columns=["agent_id", "registration_code", "region_code", "sector_id", "name"],
        )
        return frame, findings

    def _normalize_spending_full(
        self, raw_path: Path
    ) -> tuple[pd.DataFrame, list[ValidationFinding]]:
        findings: list[ValidationFinding] = []
        sample_paths = sorted(raw_path.glob("transactions_sample_*.json"))
        daily_paths = sorted(raw_path.glob("daily/**/*.json.gz"))
        if daily_paths:
            sample_paths = []
        file_limit = self._seed_limit("POLISYOS_UKRAINE_DATA_SPENDING_FILE_LIMIT")
        selected_daily_paths = self._evenly_spaced_paths(daily_paths, file_limit)
        if file_limit is not None and daily_paths and len(selected_daily_paths) < len(daily_paths):
            findings.append(
                ValidationFinding(
                    severity="warning",
                    code="capped_spending_files",
                    message=f"Normalization sampled {len(selected_daily_paths)} of {len(daily_paths)} daily Spending files due configured cap.",
                )
            )

        aggregated: dict[tuple[str, str, str], float] = {}
        for path in [*sample_paths, *selected_daily_paths]:
            data = self._load_json_payload(path)
            if not isinstance(data, list):
                continue
            for item in data:
                if not isinstance(item, dict):
                    continue
                source_agent_id = str(
                    item.get("payer_edrpou") or item.get("payer_edrpou_fact") or ""
                ).strip()
                target_agent_id = str(
                    item.get("recipt_edrpou") or item.get("recipt_edrpou_fact") or ""
                ).strip()
                if not source_agent_id or not target_agent_id:
                    continue
                period_id = self._coerce_period_id(item.get("trans_date") or item.get("doc_date"))
                amount = self._coerce_float(item.get("amount") or item.get("amount_cop"))
                key = (source_agent_id, target_agent_id, period_id)
                aggregated[key] = aggregated.get(key, 0.0) + amount

        frame = pd.DataFrame(
            [
                {
                    "source_agent_id": src,
                    "target_agent_id": dst,
                    "amount": value,
                    "period_id": period_id,
                    "registration_code": src,
                }
                for (src, dst, period_id), value in aggregated.items()
            ]
        )
        return frame, findings

    def _normalize_spending_contracts_procurement_proxy(
        self,
        raw_path: Path,
    ) -> tuple[pd.DataFrame, list[ValidationFinding]]:
        findings: list[ValidationFinding] = []
        candidate_paths = [
            raw_path / "contracts_endpoint_seed.json",
            *sorted(raw_path.glob("contracts*.json.gz")),
            *sorted(raw_path.glob("contracts*.json")),
            *sorted(raw_path.glob("contracts/**/*.json.gz")),
            *sorted(raw_path.glob("contracts/**/*.json")),
            *sorted(raw_path.glob("contracts_by_disposer/**/*.json.gz")),
            *sorted(raw_path.glob("contracts_by_disposer/**/*.json")),
        ]
        contract_paths: list[Path] = []
        seen_paths: set[Path] = set()
        for path in candidate_paths:
            if not path.exists() or not path.is_file():
                continue
            if path.name.startswith("transactions_sample_") or path.name == "package_show.json":
                continue
            resolved = path.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            contract_paths.append(path)

        file_limit = self._seed_limit("POLISYOS_UKRAINE_DATA_SPENDING_CONTRACT_FILE_LIMIT")
        selected_paths = self._evenly_spaced_paths(contract_paths, file_limit)
        if file_limit is not None and contract_paths and len(selected_paths) < len(contract_paths):
            findings.append(
                ValidationFinding(
                    severity="warning",
                    code="capped_spending_contract_files",
                    message=f"Normalization sampled {len(selected_paths)} of {len(contract_paths)} Spending contract files due configured cap.",
                )
            )

        rows: list[dict[str, object]] = []
        total_documents = 0
        documents_with_visible_supplier_id = 0
        documents_without_visible_supplier_id = 0
        prozorro_linked_documents = 0

        for path in selected_paths:
            payload = self._load_json_payload(path)
            documents = self._extract_spending_contract_documents(payload)
            for document in documents:
                buyer_agent_id = str(document.get("edrpou") or "").strip()
                if not buyer_agent_id:
                    continue
                total_documents += 1
                contract_id = str(document.get("id") or "").strip()
                tender_id = str(document.get("idTenderProzorro") or "").strip()
                if tender_id:
                    prozorro_linked_documents += 1
                amount_value = document.get("currencyAmountUAH")
                if amount_value in (None, "", "null"):
                    amount_value = document.get("amount")
                amount = self._coerce_float(amount_value)
                period_id = self._coerce_period_id(
                    document.get("signDate")
                    or document.get("documentDate")
                    or document.get("fromDate")
                )
                contractors = document.get("contractors")
                supplier_candidates: list[str | None] = []
                if isinstance(contractors, list):
                    for contractor in contractors:
                        if not isinstance(contractor, dict):
                            continue
                        identifier = str(contractor.get("identifier") or "").strip()
                        supplier_name = str(contractor.get("name") or "").strip() or None
                        if identifier.upper() == "HIDDEN":
                            identifier = ""
                        supplier_candidates.append((identifier or None, supplier_name))
                if not supplier_candidates:
                    supplier_candidates = [(None, None)]
                visible_supplier_candidates = [
                    identifier for identifier, _ in supplier_candidates if identifier
                ]
                if visible_supplier_candidates:
                    documents_with_visible_supplier_id += 1
                else:
                    documents_without_visible_supplier_id += 1
                allocation_count = len(supplier_candidates)
                allocated_amount = amount / float(allocation_count) if allocation_count else amount
                for supplier_agent_id, supplier_name in supplier_candidates:
                    rows.append(
                        {
                            "buyer_agent_id": buyer_agent_id,
                            "supplier_agent_id": supplier_agent_id,
                            "supplier_name": supplier_name,
                            "amount": allocated_amount,
                            "period_id": period_id,
                            "registration_code": buyer_agent_id,
                            "contract_id": contract_id or None,
                            "contract_count": 1,
                            "resolved_supplier_contract_count": int(bool(supplier_agent_id)),
                            "prozorro_linked_contract_count": int(bool(tender_id)),
                        }
                    )

        if not rows:
            frame = pd.DataFrame(
                columns=[
                    "buyer_agent_id",
                    "supplier_agent_id",
                    "supplier_name",
                    "amount",
                    "period_id",
                    "registration_code",
                    "contract_count",
                    "resolved_supplier_contract_count",
                    "prozorro_linked_contract_count",
                ]
            )
            return frame, findings

        frame = pd.DataFrame.from_records(rows)
        aggregated = frame.groupby(
            ["buyer_agent_id", "supplier_agent_id", "supplier_name", "period_id"],
            dropna=False,
            as_index=False,
        ).agg(
            amount=("amount", "sum"),
            contract_count=("contract_count", "sum"),
            resolved_supplier_contract_count=("resolved_supplier_contract_count", "sum"),
            prozorro_linked_contract_count=("prozorro_linked_contract_count", "sum"),
        )
        aggregated["registration_code"] = aggregated["buyer_agent_id"]
        aggregated = aggregated[
            [
                "buyer_agent_id",
                "supplier_agent_id",
                "supplier_name",
                "amount",
                "period_id",
                "registration_code",
                "contract_count",
                "resolved_supplier_contract_count",
                "prozorro_linked_contract_count",
            ]
        ]

        if documents_without_visible_supplier_id:
            findings.append(
                ValidationFinding(
                    severity="warning",
                    code="spending_contracts_hidden_supplier_ids",
                    message=(
                        f"Spending contracts proxy has no visible supplier identifier for "
                        f"{documents_without_visible_supplier_id} of {total_documents} contracts."
                    ),
                )
            )
        if prozorro_linked_documents:
            findings.append(
                ValidationFinding(
                    severity="info",
                    code="spending_contracts_linked_to_prozorro",
                    message=(
                        f"Spending contracts proxy carries idTenderProzorro for "
                        f"{prozorro_linked_documents} of {total_documents} contracts."
                    ),
                )
            )
        return aggregated, findings

    def _normalize_household_microdata(
        self,
        raw_path: Path,
    ) -> tuple[pd.DataFrame, list[ValidationFinding]]:
        findings: list[ValidationFinding] = []
        household_root = self._resolve_manual_microdata_root(raw_path)
        candidate_paths = [
            *sorted(household_root.glob("mic_doch_i_umovy*/Households_microdani_anonimni_*.xlsx")),
            *sorted(household_root.glob("mic_doch_i_umovy*/Households_microdani_anonimni_*.xls")),
        ]
        rows: list[pd.DataFrame] = []
        for path in candidate_paths:
            try:
                frame = pd.read_excel(path)
            except Exception as exc:
                findings.append(
                    ValidationFinding(
                        severity="warning",
                        code="household_microdata_read_failed",
                        message=f"Failed reading household microdata file {path.name}: {exc}",
                    )
                )
                continue
            frame = frame.rename(columns={column: str(column).strip() for column in frame.columns})
            year_col = self._first_existing_column(frame, "rik_fa_1", "RIK_FA_1", "year", "Year")
            family_col = self._first_existing_column(frame, "code_fam", "CODE_FAM")
            quarter_col = self._first_existing_column(frame, "kvart_kd", "KVART_KD")
            weight_col = self._first_existing_column(frame, "w_q", "W_Q")
            region_col = self._first_existing_column(frame, "cod_obl", "COD_OBL")
            income_col = self._first_existing_column(frame, "totalinc", "totalres", "cashinc")
            if year_col is None or family_col is None or weight_col is None or income_col is None:
                findings.append(
                    ValidationFinding(
                        severity="warning",
                        code="household_microdata_missing_columns",
                        message=f"Skipping household microdata file {path.name} because required columns are missing.",
                    )
                )
                continue
            year_series = (
                pd.to_numeric(frame[year_col], errors="coerce")
                .fillna(self._extract_year_from_name(path.name))
                .astype(int)
            )
            quarter_series = (
                pd.to_numeric(
                    frame[quarter_col] if quarter_col is not None else 4,
                    errors="coerce",
                )
                .fillna(4)
                .clip(1, 4)
                .astype(int)
            )
            region_series = frame[region_col] if region_col is not None else "00"
            normalized = pd.DataFrame(
                {
                    "household_id": [
                        f"hh::{year}::{self._normalize_registration_code(code) or self._stable_token(code)}"
                        for year, code in zip(
                            year_series.tolist(), frame[family_col].tolist(), strict=False
                        )
                    ],
                    "cell_id": [
                        f"cell::{region_code}::household_distribution"
                        for region_code in region_series.map(self._normalize_region_code).tolist()
                    ],
                    "period_id": [
                        self._quarter_to_period_id(year, quarter)
                        for year, quarter in zip(
                            year_series.tolist(), quarter_series.tolist(), strict=False
                        )
                    ],
                    "income": pd.to_numeric(frame[income_col], errors="coerce").fillna(0.0),
                    "weight": pd.to_numeric(frame[weight_col], errors="coerce").fillna(1.0),
                    "market_income": pd.to_numeric(
                        frame[
                            self._first_existing_column(frame, "cashinc", "CASHINC") or income_col
                        ],
                        errors="coerce",
                    ).fillna(0.0),
                    "total_expenditure": pd.to_numeric(
                        frame[
                            self._first_existing_column(frame, "totalexp", "TOTALEXP") or income_col
                        ],
                        errors="coerce",
                    ).fillna(0.0),
                    "region_code": region_series.map(self._normalize_region_code),
                    "source_file": path.name,
                }
            )
            normalized = normalized[normalized["household_id"].astype(str).str.len() > 0]
            rows.append(normalized)

        if not rows:
            return pd.DataFrame(
                columns=[
                    "household_id",
                    "cell_id",
                    "period_id",
                    "income",
                    "weight",
                    "market_income",
                    "total_expenditure",
                    "region_code",
                ]
            ), findings
        return pd.concat(rows, ignore_index=True), findings

    def _normalize_labor_force_microdata(
        self,
        raw_path: Path,
    ) -> tuple[pd.DataFrame, list[ValidationFinding]]:
        findings: list[ValidationFinding] = []
        labor_root = self._resolve_manual_microdata_root(raw_path)
        candidate_paths = [
            *sorted(labor_root.glob("mic_poc_rob_syly_*/LFS_*.xlsx")),
            *sorted(labor_root.glob("mic_poc_rob_syly_*/Ukr_*.xlsx")),
            *sorted(labor_root.glob("mic_poc_rob_syly_*/LFS_*.xls")),
            *sorted(labor_root.glob("mic_poc_rob_syly_*/Ukr_*.xls")),
        ]
        rows: list[pd.DataFrame] = []
        for path in candidate_paths:
            try:
                frame = pd.read_excel(path, sheet_name=0)
            except Exception as exc:
                findings.append(
                    ValidationFinding(
                        severity="warning",
                        code="labor_microdata_read_failed",
                        message=f"Failed reading labor-force microdata file {path.name}: {exc}",
                    )
                )
                continue
            frame = frame.rename(columns={column: str(column).strip() for column in frame.columns})
            id_col = self._first_existing_column(frame, "Kod_obs", "kod_obs", "KOD_OBS")
            year_col = self._first_existing_column(frame, "Rik", "Year", "year")
            weight_col = self._first_existing_column(frame, "wes_rik", "weight_year")
            region_col = self._first_existing_column(frame, "RG", "rg")
            labour_force_col = self._first_existing_column(frame, "labour_force", "LABOUR_FORCE")
            status_col = self._first_existing_column(frame, "stat_empl", "STAT_EMPL")
            informal_col = self._first_existing_column(frame, "informal_empl", "INFORMAL_EMPL")
            if id_col is None or year_col is None or labour_force_col is None:
                findings.append(
                    ValidationFinding(
                        severity="warning",
                        code="labor_microdata_missing_columns",
                        message=f"Skipping labor-force microdata file {path.name} because required columns are missing.",
                    )
                )
                continue
            year_series = (
                pd.to_numeric(frame[year_col], errors="coerce")
                .fillna(self._extract_year_from_name(path.name))
                .astype(int)
            )
            region_series = frame[region_col] if region_col is not None else "00"
            participation = (
                frame[labour_force_col].map(self._labor_force_participation_flag).astype(float)
            )
            employment = (
                frame[status_col].map(lambda value: 0.0 if self._is_nullish(value) else 1.0)
                if status_col is not None
                else 0.0
            )
            informal = (
                frame[informal_col]
                .map(lambda value: 1.0 if "неформ" in str(value).lower() else 0.0)
                .astype(float)
                if informal_col is not None
                else 0.0
            )
            normalized = pd.DataFrame(
                {
                    "household_id": [
                        f"lfs::{year}::{self._normalize_registration_code(code) or self._stable_token(code)}"
                        for year, code in zip(
                            year_series.tolist(), frame[id_col].tolist(), strict=False
                        )
                    ],
                    "cell_id": [
                        f"cell::{region_code}::labor_market"
                        for region_code in region_series.map(self._normalize_region_code).tolist()
                    ],
                    "period_id": [f"{year}-12" for year in year_series.tolist()],
                    "participation_rate": participation,
                    "weight": (
                        pd.to_numeric(frame[weight_col], errors="coerce").fillna(1.0)
                        if weight_col is not None
                        else 1.0
                    ),
                    "employment_flag": employment,
                    "informal_employment_flag": informal,
                    "region_code": region_series.map(self._normalize_region_code),
                    "source_file": path.name,
                }
            )
            normalized = normalized[normalized["household_id"].astype(str).str.len() > 0]
            rows.append(normalized)
        if not rows:
            return pd.DataFrame(
                columns=[
                    "household_id",
                    "cell_id",
                    "period_id",
                    "participation_rate",
                    "weight",
                    "employment_flag",
                    "informal_employment_flag",
                    "region_code",
                ]
            ), findings
        return pd.concat(rows, ignore_index=True), findings

    def _normalize_pfu_debt(
        self,
        raw_path: Path,
    ) -> tuple[pd.DataFrame, list[ValidationFinding]]:
        findings: list[ValidationFinding] = []
        candidate_paths = [
            *sorted(raw_path.glob("*.xlsx")),
            *sorted(raw_path.glob("*.xls")),
            *sorted(raw_path.glob("*.csv")),
        ]
        rows: list[dict[str, object]] = []
        for path in candidate_paths:
            try:
                frame = (
                    pd.read_csv(path, header=None, sep=None, engine="python", encoding="utf-8-sig")
                    if path.suffix.lower() == ".csv"
                    else pd.read_excel(path, header=None)
                )
            except Exception as exc:
                findings.append(
                    ValidationFinding(
                        severity="warning",
                        code="pfu_debt_read_failed",
                        message=f"Failed reading PFU debt file {path.name}: {exc}",
                    )
                )
                continue
            rows.extend(
                self._extract_pfu_debt_rows(
                    frame, period_id=self._extract_period_id_from_name(path.name)
                )
            )
        frame = pd.DataFrame.from_records(rows)
        if frame.empty:
            return pd.DataFrame(
                columns=[
                    "registration_code",
                    "period_id",
                    "arrears_amount",
                    "debt_amount",
                    "region_code",
                ]
            ), findings
        aggregated = frame.groupby(["registration_code", "period_id"], as_index=False).agg(
            arrears_amount=("arrears_amount", "sum"),
            debt_amount=("debt_amount", "sum"),
            region_code=("region_code", "first"),
        )
        return aggregated, findings

    def _normalize_wage_arrears(
        self,
        raw_path: Path,
    ) -> tuple[pd.DataFrame, list[ValidationFinding]]:
        findings: list[ValidationFinding] = []
        extracted_paths = [
            *sorted(raw_path.glob("*.xlsx")),
            *sorted(raw_path.glob("*.xls")),
            *sorted(raw_path.glob("*.csv")),
        ]
        archive_paths = sorted(raw_path.glob("*.7z"))
        if not extracted_paths and archive_paths:
            seven_zip = shutil.which("7z") or shutil.which("7zz")
            if seven_zip is not None:
                with tempfile.TemporaryDirectory(prefix="wage_arrears_extract_") as tmp_dir:
                    for archive_path in archive_paths:
                        subprocess.run(
                            [seven_zip, "x", "-y", f"-o{tmp_dir}", str(archive_path)],
                            check=True,
                            capture_output=True,
                        )
                    extracted_root = Path(tmp_dir)
                    extracted_paths = [
                        *sorted(extracted_root.rglob("*.xlsx")),
                        *sorted(extracted_root.rglob("*.xls")),
                        *sorted(extracted_root.rglob("*.csv")),
                    ]
                    frame, parse_findings = self._extract_wage_arrears_frame(extracted_paths)
                    findings.extend(parse_findings)
                    if not frame.empty:
                        return frame, findings
            findings.append(
                ValidationFinding(
                    severity="warning",
                    code="wage_arrears_proxy_from_pfu_debt",
                    message=(
                        "Wage arrears raw archive could not be parsed directly; using PFU debt proxy "
                        "for first-pass D3 execution."
                    ),
                )
            )
        else:
            frame, parse_findings = self._extract_wage_arrears_frame(extracted_paths)
            findings.extend(parse_findings)
            if not frame.empty:
                return frame, findings

        pfu_dir = raw_path.parent / "pfu_debt_registry"
        if pfu_dir.exists():
            pfu_frame, pfu_findings = self._normalize_pfu_debt(pfu_dir)
            findings.extend(pfu_findings)
            if not pfu_frame.empty:
                proxy = pfu_frame[["registration_code", "period_id", "region_code"]].copy()
                proxy["wage_arrears_amount"] = pfu_frame["arrears_amount"].astype(float)
                proxy["agent_id"] = proxy["registration_code"].map(
                    lambda value: f"agent::{self._stable_token(value)}"
                )
                return proxy, findings

        return pd.DataFrame(
            columns=[
                "agent_id",
                "registration_code",
                "period_id",
                "wage_arrears_amount",
                "region_code",
            ]
        ), findings

    def _normalize_distress_events(
        self,
        raw_path: Path,
    ) -> tuple[pd.DataFrame, list[ValidationFinding]]:
        findings: list[ValidationFinding] = []
        raw_root = self._resolve_distress_raw_root(raw_path)
        rows: list[dict[str, object]] = []

        bankruptcy_path = (
            raw_root / "bankruptcy_notices" / "001_vidomosti-pro-spravi-pro-bankrutstvo.csv"
        )
        if bankruptcy_path.exists():
            bankruptcy = pd.read_csv(
                bankruptcy_path,
                sep="\t",
                encoding="utf-8-sig",
                quotechar='"',
            )
            bankruptcy.columns = [str(column).strip().strip('"') for column in bankruptcy.columns]
            for row in bankruptcy.to_dict(orient="records"):
                registration_code = self._normalize_registration_code(row.get("firm_edrpou"))
                if registration_code is None:
                    continue
                rows.append(
                    {
                        "registration_code": registration_code,
                        "period_id": self._coerce_period_id(row.get("date")),
                        "event_count": 1.0,
                        "event_flag": 1.0,
                        "region_code": "00",
                    }
                )
        debtor_zip = raw_root / "debtor_register" / "001_29-ex_csv_erb.zip"
        if debtor_zip.exists():
            with ZipFile(debtor_zip) as archive:
                member = archive.namelist()[0]
                with archive.open(member) as handle:
                    for debtor_chunk in pd.read_csv(
                        handle,
                        sep=";",
                        encoding="cp1251",
                        chunksize=100_000,
                        low_memory=False,
                    ):
                        debtor_chunk.columns = [
                            str(column).strip() for column in debtor_chunk.columns
                        ]
                        if "DEBTOR_CODE" not in debtor_chunk.columns:
                            continue
                        for value in debtor_chunk["DEBTOR_CODE"].tolist():
                            registration_code = self._normalize_registration_code(value)
                            if registration_code is None:
                                continue
                            rows.append(
                                {
                                    "registration_code": registration_code,
                                    "period_id": self._extract_period_id_from_name(debtor_zip.name),
                                    "event_count": 1.0,
                                    "event_flag": 1.0,
                                    "region_code": "00",
                                }
                            )
        frame = pd.DataFrame.from_records(rows)
        if frame.empty:
            return pd.DataFrame(
                columns=[
                    "registration_code",
                    "period_id",
                    "event_count",
                    "event_flag",
                    "region_code",
                ]
            ), findings
        aggregated = frame.groupby(["registration_code", "period_id"], as_index=False).agg(
            event_count=("event_count", "sum"),
            event_flag=("event_flag", "max"),
            region_code=("region_code", "first"),
        )
        return aggregated, findings

    def _normalize_logistics_mobility_displacement(
        self,
        raw_path: Path,
    ) -> tuple[pd.DataFrame, list[ValidationFinding]]:
        findings: list[ValidationFinding] = []
        candidate_roots = [
            raw_path,
            raw_path / "border_crossing_points_public",
            raw_path.parent / "border_crossing_points_public",
        ]
        candidate_paths: list[Path] = []
        for candidate_root in candidate_roots:
            if not candidate_root.exists():
                continue
            candidate_paths.extend(sorted(candidate_root.glob("*.xlsx")))
            candidate_paths.extend(sorted(candidate_root.glob("*.xls")))

        rows: list[pd.DataFrame] = []
        seen: set[Path] = set()
        for path in candidate_paths:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                frame = pd.read_excel(path, sheet_name=0)
            except Exception as exc:
                findings.append(
                    ValidationFinding(
                        severity="warning",
                        code="logistics_mobility_read_failed",
                        message=f"Failed reading logistics mobility file {path.name}: {exc}",
                    )
                )
                continue
            frame = frame.rename(columns={column: str(column).strip() for column in frame.columns})
            region_col = self._detect_region_like_column(frame)
            if region_col is None:
                findings.append(
                    ValidationFinding(
                        severity="warning",
                        code="logistics_mobility_region_column_missing",
                        message=f"Could not infer region column for logistics mobility file {path.name}.",
                    )
                )
                continue
            region_codes = frame[region_col].map(self._normalize_region_code)
            valid = region_codes != "00"
            if not valid.any():
                findings.append(
                    ValidationFinding(
                        severity="warning",
                        code="logistics_mobility_no_resolved_regions",
                        message=f"No resolvable regions found in logistics mobility file {path.name}.",
                    )
                )
                continue
            period_id = self._extract_period_id_from_name(path.name)
            aggregated = (
                pd.DataFrame({"region_code": region_codes[valid]})
                .groupby("region_code", as_index=False)
                .size()
                .rename(columns={"size": "mobility_pressure"})
            )
            aggregated["period_id"] = period_id
            aggregated["cell_id"] = aggregated["region_code"].map(
                lambda value: f"cell::{value}::logistics_mobility"
            )
            aggregated["source_file"] = path.name
            rows.append(
                aggregated[
                    ["cell_id", "period_id", "mobility_pressure", "region_code", "source_file"]
                ]
            )

        if not rows:
            return pd.DataFrame(
                columns=["cell_id", "period_id", "mobility_pressure", "region_code"]
            ), findings
        combined = pd.concat(rows, ignore_index=True)
        aggregated = combined.groupby(["cell_id", "period_id", "region_code"], as_index=False).agg(
            mobility_pressure=("mobility_pressure", "sum"),
            source_file=("source_file", "first"),
        )
        return aggregated, findings

    def _normalize_land_cadastre(
        self,
        raw_path: Path,
    ) -> tuple[pd.DataFrame, list[ValidationFinding]]:
        findings: list[ValidationFinding] = []
        candidate_paths = [
            *sorted(raw_path.glob("*.xlsx")),
            *sorted(raw_path.glob("*.xls")),
        ]
        rows: list[dict[str, object]] = []
        for path in candidate_paths:
            try:
                frame = pd.read_excel(path, header=None, sheet_name=0)
            except Exception as exc:
                findings.append(
                    ValidationFinding(
                        severity="warning",
                        code="land_cadastre_read_failed",
                        message=f"Failed reading land cadastre file {path.name}: {exc}",
                    )
                )
                continue
            title_candidates = [
                str(value).strip()
                for value in frame.iloc[:3, :3].stack().tolist()
                if not self._is_nullish(value)
            ]
            title_text = " ".join(title_candidates)
            region_code = self._normalize_region_code(title_text)
            period_id = self._extract_period_id_from_name(path.name)
            numeric = frame.apply(pd.to_numeric, errors="coerce")
            land_use_proxy = float(numeric.fillna(0.0).sum().sum())
            if land_use_proxy <= 0.0:
                findings.append(
                    ValidationFinding(
                        severity="warning",
                        code="land_cadastre_zero_proxy",
                        message=f"Land cadastre file {path.name} produced zero proxy mass and was skipped.",
                    )
                )
                continue
            rows.append(
                {
                    "cell_id": f"cell::{region_code}::land_use_proxy",
                    "period_id": period_id,
                    "land_use_proxy": land_use_proxy,
                    "region_code": region_code,
                    "source_file": path.name,
                }
            )
        if not rows:
            return pd.DataFrame(
                columns=["cell_id", "period_id", "land_use_proxy", "region_code"]
            ), findings
        return pd.DataFrame.from_records(rows), findings

    def _normalize_prozorro_full(
        self, raw_path: Path
    ) -> tuple[pd.DataFrame, list[ValidationFinding]]:
        detail_paths = sorted(raw_path.glob("contracts_details/page_*.json"))
        if detail_paths:
            rows: list[dict[str, object]] = []
            findings: list[ValidationFinding] = []
            for path in detail_paths:
                payload = self._load_json_payload(path)
                if not isinstance(payload, dict):
                    continue
                contracts = payload.get("contracts", [])
                if not isinstance(contracts, list):
                    continue
                for contract in contracts:
                    if not isinstance(contract, dict):
                        continue
                    buyer = contract.get("buyer") or {}
                    suppliers = contract.get("suppliers") or []
                    if not isinstance(buyer, dict):
                        buyer = {}
                    if not isinstance(suppliers, list):
                        suppliers = []
                    buyer_identifier = (
                        (buyer.get("identifier") or {})
                        if isinstance(buyer.get("identifier"), dict)
                        else {}
                    ).get("id")
                    supplier_identifiers = [
                        (
                            (supplier.get("identifier") or {})
                            if isinstance(supplier.get("identifier"), dict)
                            else {}
                        ).get("id")
                        for supplier in suppliers
                        if isinstance(supplier, dict)
                    ]
                    if not supplier_identifiers:
                        supplier_identifiers = [None]
                    for supplier_identifier in supplier_identifiers:
                        rows.append(
                            {
                                "buyer_agent_id": str(buyer_identifier).strip() or None,
                                "supplier_agent_id": str(supplier_identifier).strip() or None,
                                "amount": self._coerce_float(
                                    (contract.get("value") or {}).get("amount")
                                ),
                                "period_id": self._coerce_period_id(
                                    contract.get("dateSigned")
                                    or contract.get("date")
                                    or contract.get("dateModified")
                                ),
                                "registration_code": str(
                                    buyer_identifier or contract.get("id") or ""
                                ).strip(),
                                "contract_id": str(contract.get("id") or "").strip(),
                            }
                        )
            frame = pd.DataFrame(rows)
            return frame, findings

        findings = [
            ValidationFinding(
                severity="warning",
                code="prozorro_feed_without_contract_details",
                message="Normalization uses contracts feed pages; buyer/supplier and amount require detail hydration that is not available in current raw layer.",
            )
        ]
        page_paths = sorted(raw_path.glob("contracts_feed/page_*.json")) or sorted(
            raw_path.glob("page_*.json")
        )
        seed_paths = [path for path in [raw_path / "contracts_seed_page.json"] if path.exists()]
        page_limit = self._seed_limit("POLISYOS_UKRAINE_DATA_PROZORRO_PAGE_LIMIT")
        selected_pages = self._evenly_spaced_paths(page_paths, page_limit)
        if page_limit is not None and page_paths and len(selected_pages) < len(page_paths):
            findings.append(
                ValidationFinding(
                    severity="warning",
                    code="capped_prozorro_pages",
                    message=f"Normalization sampled {len(selected_pages)} of {len(page_paths)} Prozorro feed pages due configured cap.",
                )
            )

        period_counts: dict[str, int] = {}
        for path in [*seed_paths, *selected_pages]:
            payload = self._load_json_payload(path)
            if not isinstance(payload, dict):
                continue
            for item in payload.get("data", []):
                if not isinstance(item, dict):
                    continue
                period_id = self._coerce_period_id(item.get("dateModified"))
                period_counts[period_id] = period_counts.get(period_id, 0) + 1
        frame = pd.DataFrame(
            [
                {
                    "buyer_agent_id": None,
                    "supplier_agent_id": None,
                    "amount": float(count),
                    "period_id": period_id,
                    "registration_code": f"contracts_feed::{period_id}",
                    "contract_count": int(count),
                }
                for period_id, count in sorted(period_counts.items())
            ]
        )
        return frame, findings

    def _normalize_macro_panel(
        self, raw_path: Path
    ) -> tuple[pd.DataFrame, list[ValidationFinding]]:
        rows: list[dict[str, object]] = []
        for path in sorted(raw_path.glob("*.json")):
            if path.name.endswith("_package_show.json"):
                continue
            payload = self._load_json_payload(path)
            if path.name.startswith("nbu_exchange_") and isinstance(payload, list):
                for record in payload:
                    if not isinstance(record, dict):
                        continue
                    currency = str(record.get("cc") or "UNK")
                    rows.append(
                        {
                            "period_id": self._coerce_period_id(record.get("exchangedate")),
                            "metric_id": f"{path.stem}:{currency}:rate",
                            "observed_value": self._coerce_float(
                                record.get("rate_per_unit") or record.get("rate")
                            ),
                            "region_code": "UA00000000000000000",
                        }
                    )
                continue
            rows.extend(self._extract_sdmx_rows(payload, metric_prefix=path.stem))
        frame = pd.DataFrame(rows)
        return frame, []

    def _normalize_dps_financials(
        self, raw_path: Path
    ) -> tuple[pd.DataFrame, list[ValidationFinding]]:
        findings: list[ValidationFinding] = []
        record_limit = self._seed_limit("POLISYOS_UKRAINE_DATA_DPS_RECORD_LIMIT")
        balance_rows = self._parse_dps_zip_records(
            raw_path / "f_i_ric_2022.zip",
            limit=record_limit,
            field_map={
                "registration_code": "FIRM_EDRPOU",
                "assets": "A1300",
                "liabilities": "A1595",
            },
        )
        income_rows = self._parse_dps_zip_records(
            raw_path / "f_ii_ric_2022.zip",
            limit=record_limit,
            field_map={
                "registration_code": "FIRM_EDRPOU",
                "revenue": "B2000",
            },
        )
        if record_limit is not None and balance_rows and len(balance_rows) >= record_limit:
            findings.append(
                ValidationFinding(
                    severity="warning",
                    code="capped_dps_balance_records",
                    message=f"Normalization capped DPS balance records at {record_limit}.",
                )
            )
        if record_limit is not None and income_rows and len(income_rows) >= record_limit:
            findings.append(
                ValidationFinding(
                    severity="warning",
                    code="capped_dps_income_records",
                    message=f"Normalization capped DPS income records at {record_limit}.",
                )
            )
        findings.append(
            ValidationFinding(
                severity="warning",
                code="dps_employment_not_available",
                message=(
                    "The provisional DPS substitute does not expose a trusted employment-count field; "
                    "employees were set to 0.0 instead of misusing FIRM_TELORG telephone metadata."
                ),
            )
        )

        frame = pd.DataFrame(balance_rows)
        if frame.empty:
            frame = pd.DataFrame(
                columns=["registration_code", "assets", "liabilities", "employees"]
            )
        income_frame = pd.DataFrame(income_rows)
        if not income_frame.empty:
            frame = frame.merge(income_frame, on="registration_code", how="outer")
        if "registration_code" not in frame.columns:
            frame["registration_code"] = []
        frame["agent_id"] = frame["registration_code"].map(
            lambda value: f"agent::{self._stable_token(value)}"
        )
        frame["period_id"] = "2022-12"
        for column in ("revenue", "assets", "liabilities", "employees"):
            if column not in frame.columns:
                frame[column] = 0.0
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
        return frame[
            [
                "agent_id",
                "registration_code",
                "period_id",
                "revenue",
                "assets",
                "liabilities",
                "employees",
            ]
        ], findings

    def _parse_dps_zip_records(
        self,
        archive_path: Path,
        *,
        limit: int | None,
        field_map: dict[str, str],
    ) -> list[dict[str, object]]:
        if not archive_path.exists():
            return []
        rows: list[dict[str, object]] = []
        with ZipFile(archive_path) as archive:
            for member in archive.namelist():
                if limit is not None and len(rows) >= limit:
                    break
                if not member.lower().endswith(".xml"):
                    continue
                with archive.open(member) as handle:
                    payload = handle.read().decode("utf-8", "ignore")
                row: dict[str, object] = {}
                for out_key, xml_key in field_map.items():
                    row[out_key] = self._extract_xml_tag(payload, xml_key)
                registration_code = str(row.get("registration_code") or "").strip()
                if registration_code:
                    rows.append(row)
        return rows

    @staticmethod
    def _seed_limit(env_name: str) -> int | None:
        raw = os.getenv(env_name)
        if raw is None:
            return None
        try:
            value = int(raw)
        except ValueError:
            return None
        if value <= 0:
            return None
        return max(1, value)

    @staticmethod
    def _evenly_spaced_paths(paths: list[Path], limit: int | None) -> list[Path]:
        if limit is None or len(paths) <= limit:
            return paths
        if limit <= 1:
            return [paths[-1]]
        step = (len(paths) - 1) / float(limit - 1)
        indices = sorted({min(len(paths) - 1, round(i * step)) for i in range(limit)})
        return [paths[index] for index in indices]

    @staticmethod
    def _load_json_payload(path: Path) -> object:
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                return json.load(handle)
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _extract_spending_contract_documents(payload: object) -> list[dict[str, object]]:
        if isinstance(payload, dict):
            documents = payload.get("documents")
            if isinstance(documents, list):
                return [item for item in documents if isinstance(item, dict)]
            data = payload.get("data")
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []

    @staticmethod
    def _extract_record_dicts(payload: object) -> list[dict[str, object]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for value in payload.values():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _first_present(record: dict[str, object], *keys: str) -> object:
        for key in keys:
            value = record.get(key)
            if value not in (None, "", "null"):
                return value
        return None

    @staticmethod
    def _first_numeric_value(record: dict[str, object]) -> float | None:
        for key, value in record.items():
            if key.lower() in {"year", "month", "quarter", "period", "period_id"}:
                continue
            try:
                if value in (None, "", "null"):
                    continue
                return float(str(value).replace(",", "."))
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _coerce_float(value: object) -> float:
        try:
            return float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _coerce_positive_int(value: object, *, default: int) -> int:
        try:
            parsed = int(str(value))
        except (TypeError, ValueError):
            return default
        return parsed if parsed > 0 else default

    @staticmethod
    def _coerce_period_id(value: object) -> str:
        text = str(value or "").strip()
        if len(text) >= 7 and text[4] == "-":
            return text[:7]
        if len(text) == 4 and text.isdigit():
            return f"{text}-12"
        if len(text) >= 10 and text[2] == "." and text[5] == ".":
            return f"{text[6:10]}-{text[3:5]}"
        if len(text) == 8 and text.isdigit():
            return f"{text[:4]}-{text[4:6]}"
        return "2025-01"

    @staticmethod
    def _region_from_registration(value: object) -> str:
        if value is None:
            return "00"
        tail = str(value).split(";")[-1]
        digits = "".join(ch for ch in tail if ch.isdigit())
        if len(digits) >= 2:
            return digits[:2]
        return "00"

    @staticmethod
    def _xml_child_text(elem: ET.Element, tag: str) -> str | None:
        child = elem.find(tag)
        if child is None or child.text is None:
            return None
        return child.text.strip()

    @staticmethod
    def _extract_xml_tag(payload: str, tag: str) -> str | None:
        match = re.search(rf"<{tag}>(.*?)</{tag}>", payload, flags=re.S)
        if match is None:
            return None
        return html.unescape(match.group(1).strip())

    @staticmethod
    def _first_existing_column(frame: pd.DataFrame, *candidates: str) -> str | None:
        lookup = {str(column).strip().lower(): str(column) for column in frame.columns}
        for candidate in candidates:
            resolved = lookup.get(candidate.strip().lower())
            if resolved is not None:
                return resolved
        return None

    @staticmethod
    def _is_nullish(value: object) -> bool:
        if value is None:
            return True
        text = str(value).strip()
        return text == "" or text.upper() in {"#NULL!", "NULL", "NAN", "NONE"}

    @staticmethod
    def _normalize_registration_code(value: object) -> str | None:
        digits = "".join(ch for ch in str(value or "") if ch.isdigit())
        if len(digits) >= 5:
            return digits
        return None

    @staticmethod
    def _normalize_region_code(value: object) -> str:
        raw_text = str(value or "").strip()
        text = raw_text.lower().replace("область", "").replace('"', "")
        text = " ".join(text.split())
        if any(char.isalpha() for char in raw_text):
            direct = _UKRAINE_OBLAST_CODE_MAP.get(text)
            if direct is not None:
                return direct
            for key, code in _UKRAINE_OBLAST_CODE_MAP.items():
                if key in text:
                    return code
                stem = key.replace("м. ", "").rstrip()
                if len(stem) > 4 and stem[:-2] in text:
                    return code
        digits = "".join(ch for ch in raw_text if ch.isdigit())
        if len(digits) >= 2:
            return digits[:2]
        if len(digits) == 1:
            return digits.zfill(2)
        return "00"

    def _detect_region_like_column(self, frame: pd.DataFrame) -> str | None:
        best_column: str | None = None
        best_score = 0
        for column in frame.columns:
            series = frame[column].dropna()
            if series.empty:
                continue
            text_values = series.astype(str).map(str.strip)
            alpha_score = sum(
                any(char.isalpha() for char in value) for value in text_values.tolist()
            )
            if alpha_score <= 0:
                continue
            region_score = sum(
                1 for value in text_values.tolist() if self._normalize_region_code(value) != "00"
            )
            if region_score > best_score:
                best_score = region_score
                best_column = str(column)
        return best_column if best_score > 0 else None

    @staticmethod
    def _extract_year_from_name(name: str) -> int:
        match = re.search(r"(20\d{2})", name)
        if match is not None:
            return int(match.group(1))
        return 2021

    def _extract_period_id_from_name(self, name: str) -> str:
        dotted_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", name)
        if dotted_match is not None:
            return self._coerce_period_id(dotted_match.group(1))
        compact_match = re.search(r"((?:19|20)\d{2})(\d{2})", name)
        if compact_match is not None:
            return f"{compact_match.group(1)}-{compact_match.group(2)}"
        year = self._extract_year_from_name(name)
        return f"{year}-12"

    @staticmethod
    def _quarter_to_period_id(year: int, quarter: int) -> str:
        month_lookup = {1: "03", 2: "06", 3: "09", 4: "12"}
        return f"{int(year):04d}-{month_lookup.get(int(quarter), '12')}"

    @staticmethod
    def _labor_force_participation_flag(value: object) -> int:
        text = str(value or "").strip().lower()
        if not text or text == "#null!":
            return 0
        if (
            "поза робочою силою" in text
            or "неактив" in text
            or "не входять до робочої сили" in text
        ):
            return 0
        return 1

    def _resolve_manual_microdata_root(self, raw_path: Path) -> Path:
        candidates = [
            raw_path,
            raw_path / "manual_microdata_drop",
            raw_path.parent / "manual_microdata_drop",
        ]
        for candidate in candidates:
            if candidate.exists() and any(candidate.glob("mic_doch_i_umovy*")):
                return candidate
            if candidate.exists() and any(candidate.glob("mic_poc_rob_syly_*")):
                return candidate
        return raw_path

    def _resolve_distress_raw_root(self, raw_path: Path) -> Path:
        candidates = [raw_path, raw_path.parent, raw_path.parent.parent]
        for candidate in candidates:
            if (candidate / "bankruptcy_notices").exists() or (
                candidate / "debtor_register"
            ).exists():
                return candidate
        return raw_path

    def _extract_pfu_debt_rows(
        self,
        frame: pd.DataFrame,
        *,
        period_id: str,
    ) -> list[dict[str, object]]:
        if frame.empty:
            return []
        normalized = frame.copy()
        normalized.columns = list(range(normalized.shape[1]))
        header_row_index: int | None = None
        edrpou_col: int | None = None
        debt_col: int | None = None
        region_col = 0
        for row_index in range(len(normalized)):
            values = [
                str(value or "").strip().lower() for value in normalized.iloc[row_index].tolist()
            ]
            if any("єдрпоу" in value for value in values):
                header_row_index = row_index
                for idx, value in enumerate(values):
                    if "єдрпоу" in value and edrpou_col is None:
                        edrpou_col = idx
                    if "станом на звітну дату" in value and debt_col is None:
                        debt_col = idx
                    if "код регіону" in value:
                        region_col = idx
                if debt_col is None:
                    for follow_row in range(row_index + 1, min(len(normalized), row_index + 4)):
                        follow_values = [
                            str(value or "").strip().lower()
                            for value in normalized.iloc[follow_row].tolist()
                        ]
                        for idx, value in enumerate(follow_values):
                            if "станом на звітну дату" in value or "сума заборгованості" in value:
                                debt_col = idx
                                break
                        if debt_col is not None:
                            break
                break
        if header_row_index is None or edrpou_col is None or debt_col is None:
            return []

        rows: list[dict[str, object]] = []
        for row_index in range(header_row_index + 1, len(normalized)):
            row = normalized.iloc[row_index]
            registration_code = self._normalize_registration_code(row.iloc[edrpou_col])
            if registration_code is None:
                continue
            debt_amount = self._coerce_float(row.iloc[debt_col])
            rows.append(
                {
                    "registration_code": registration_code,
                    "period_id": period_id,
                    "arrears_amount": debt_amount,
                    "debt_amount": debt_amount,
                    "region_code": self._normalize_region_code(row.iloc[region_col]),
                }
            )
        return rows

    def _extract_wage_arrears_frame(
        self,
        extracted_paths: list[Path],
    ) -> tuple[pd.DataFrame, list[ValidationFinding]]:
        findings: list[ValidationFinding] = []
        rows: list[dict[str, object]] = []
        for path in extracted_paths:
            try:
                frame = (
                    pd.read_csv(path, header=None, sep=None, engine="python", encoding="utf-8-sig")
                    if path.suffix.lower() == ".csv"
                    else pd.read_excel(path, header=None)
                )
            except Exception as exc:
                findings.append(
                    ValidationFinding(
                        severity="warning",
                        code="wage_arrears_read_failed",
                        message=f"Failed reading wage arrears file {path.name}: {exc}",
                    )
                )
                continue
            header_row_index: int | None = None
            name_col: int | None = None
            registration_col: int | None = None
            amount_col: int | None = None
            for row_index in range(len(frame)):
                values = [
                    str(value or "").strip().lower() for value in frame.iloc[row_index].tolist()
                ]
                if any("назва" in value for value in values) and any(
                    "заборг" in value or "сума" in value for value in values
                ):
                    header_row_index = row_index
                    for idx, value in enumerate(values):
                        if "єдрпоу" in value and registration_col is None:
                            registration_col = idx
                        if "назва" in value and name_col is None:
                            name_col = idx
                        if "сума" in value and amount_col is None:
                            amount_col = idx
                    break
            if header_row_index is None or name_col is None or amount_col is None:
                continue
            period_id = self._extract_period_id_from_name(path.name)
            for row_index in range(header_row_index + 1, len(frame)):
                row = frame.iloc[row_index]
                name = str(row.iloc[name_col] or "").strip()
                if not name:
                    continue
                registration_code = (
                    self._normalize_registration_code(row.iloc[registration_col])
                    if registration_col is not None
                    else None
                )
                synthetic_registration = registration_code or f"name::{self._stable_token(name)}"
                rows.append(
                    {
                        "agent_id": f"agent::{self._stable_token(synthetic_registration)}",
                        "registration_code": synthetic_registration,
                        "period_id": period_id,
                        "wage_arrears_amount": self._coerce_float(row.iloc[amount_col]),
                        "region_code": "00",
                    }
                )
        if not rows:
            return pd.DataFrame(
                columns=[
                    "agent_id",
                    "registration_code",
                    "period_id",
                    "wage_arrears_amount",
                    "region_code",
                ]
            ), findings
        frame = pd.DataFrame.from_records(rows)
        aggregated = frame.groupby(
            ["agent_id", "registration_code", "period_id"], as_index=False
        ).agg(
            wage_arrears_amount=("wage_arrears_amount", "sum"),
            region_code=("region_code", "first"),
        )
        return aggregated, findings

    def _edr_registration_code(self, elem: ET.Element, *, zip_name: str) -> str:
        if "FOP" not in zip_name:
            return (
                self._xml_child_text(elem, "EDRPOU") or self._xml_child_text(elem, "RECORD") or ""
            ).strip()
        exchange_answers = elem.findall("./EXCHANGE_DATA/EXCHANGE_ANSWER")
        for answer in exchange_answers:
            start_num = self._xml_child_text(answer, "START_NUM")
            if start_num:
                return start_num
        return (self._xml_child_text(elem, "RECORD") or "").strip()

    def _extract_sdmx_rows(self, payload: object, *, metric_prefix: str) -> list[dict[str, object]]:
        if not isinstance(payload, dict):
            return []
        data_node = payload.get("data")
        if not isinstance(data_node, dict):
            return []
        data_sets = data_node.get("dataSets")
        structures = data_node.get("structures")
        if not isinstance(data_sets, list) or not data_sets:
            return []
        if not isinstance(structures, list) or not structures:
            return []
        structure = structures[0]
        dimensions = structure.get("dimensions", {})
        series_dims = dimensions.get("series", [])
        obs_dims = dimensions.get("observation", [])
        time_values = []
        if obs_dims:
            time_values = [
                item.get("value") or item.get("id") for item in obs_dims[0].get("values", [])
            ]
        rows: list[dict[str, object]] = []
        for dataset in data_sets:
            if not isinstance(dataset, dict):
                continue
            series_map = dataset.get("series", {})
            if not isinstance(series_map, dict):
                continue
            for series_key, series_payload in series_map.items():
                if not isinstance(series_payload, dict):
                    continue
                series_parts = [int(part) for part in str(series_key).split(":") if part != ""]
                dim_values: dict[str, str] = {}
                for index, dim in enumerate(series_dims):
                    values = dim.get("values", [])
                    code = ""
                    if index < len(series_parts) and series_parts[index] < len(values):
                        value_node = values[series_parts[index]]
                        code = str(value_node.get("id") or value_node.get("value") or "")
                    dim_values[str(dim.get("id") or f"dim_{index}")] = code
                observations = series_payload.get("observations", {})
                if not isinstance(observations, dict):
                    continue
                for obs_key, obs_value in observations.items():
                    obs_index = int(obs_key)
                    if obs_index >= len(time_values):
                        continue
                    observed = None
                    if isinstance(obs_value, list) and obs_value:
                        observed = self._coerce_float(obs_value[0])
                    elif obs_value is not None:
                        observed = self._coerce_float(obs_value)
                    if observed is None:
                        continue
                    indicator = dim_values.get("INDICATOR") or metric_prefix
                    price_type = dim_values.get("PRICE_TYPE")
                    breakdown = dim_values.get("BREAKDOWN")
                    metric_parts = [metric_prefix, indicator]
                    if price_type:
                        metric_parts.append(price_type)
                    if breakdown and breakdown != "_T":
                        metric_parts.append(breakdown)
                    rows.append(
                        {
                            "period_id": self._coerce_period_id(time_values[obs_index]),
                            "metric_id": ":".join(metric_parts),
                            "observed_value": observed,
                            "region_code": dim_values.get("REGION") or "UA00000000000000000",
                        }
                    )
        return rows

    def _ensure_standard_columns(
        self,
        frame: pd.DataFrame,
        source: SourceConfig,
        snapshot: SourceSnapshotManifest,
    ) -> pd.DataFrame:
        result = frame.copy()
        if "source_snapshot_id" not in result.columns:
            result["source_snapshot_id"] = snapshot.raw_artifacts[0].sha256
        if "schema_version" not in result.columns:
            result["schema_version"] = "1.0"
        if source.period_column not in result.columns:
            result[source.period_column] = "2025-01"
        if "agent_id" not in result.columns and "registration_code" in result.columns:
            result["agent_id"] = result["registration_code"].map(
                lambda value: (
                    f"agent::{self._stable_token(value)}" if not self._is_nullish(value) else None
                )
            )
        if source.stage_id == StageId.D0_P0 and source.source_id == "edr_current":
            if "agent_id" not in result.columns:
                if "registration_code" in result.columns:
                    result["agent_id"] = result["registration_code"].map(
                        lambda value: f"agent::{self._stable_token(value)}"
                    )
                else:
                    result["agent_id"] = [f"agent::{index:08d}" for index in range(len(result))]
        if "record_hash" not in result.columns:
            result["record_hash"] = [
                self._stable_row_hash(row) for row in result.to_dict(orient="records")
            ]
        return result

    @staticmethod
    def _stable_token(value: object) -> str:
        digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()
        return digest[:16]

    @staticmethod
    def _stable_row_hash(row: dict[str, object]) -> str:
        payload = json.dumps(row, ensure_ascii=True, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_default_adapter_registry() -> dict[str, SourceAdapter]:
    """Return the default adapter registry used by the Ukraine data stack."""

    return {"tabular": TabularSourceAdapter()}


__all__ = [
    "AgentIdentityResolver",
    "SourceAdapter",
    "SourceExecutionContext",
    "TabularSourceAdapter",
    "build_default_adapter_registry",
]
