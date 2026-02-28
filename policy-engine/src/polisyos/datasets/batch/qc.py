"""Stage 7: QC checks for datasets pipeline."""

from __future__ import annotations

import json
import random
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.batch_common.qc import QCCheck, QCReport, evaluate_fail_fast, write_qc_report
from polisyos.datasets.batch.config import DatasetBatchConfig



def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, "r", encoding="utf-8") as fh:
        return sum(1 for _ in fh)


def _latest_manifest(source_dir: Path) -> Path | None:
    if not source_dir.exists():
        return None
    snaps = sorted([p for p in source_dir.iterdir() if p.is_dir()])
    if not snaps:
        return None
    manifest = snaps[-1] / "manifest.json"
    return manifest if manifest.exists() else None


def run_qc(config: DatasetBatchConfig, *, fail_fast: bool | None = None) -> QCReport:
    started_at = datetime.now(UTC).isoformat()
    checks: list[QCCheck] = []
    metrics: dict[str, float | int] = {}

    # 1) Raw manifest count parity
    source_dirs = [p for p in config.raw_dir.iterdir() if p.is_dir()] if config.raw_dir.exists() else []
    parity_failures = 0
    for source_dir in source_dirs:
        manifest_path = _latest_manifest(source_dir)
        if not manifest_path:
            continue
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        payload = Path(manifest.get("payload", ""))
        declared = int(manifest.get("count", 0))
        actual = _line_count(payload)
        if declared != actual:
            parity_failures += 1

    checks.append(
        QCCheck(
            name="manifest_count_parity",
            passed=parity_failures == 0,
            threshold=0,
            value=parity_failures,
            message="Number of raw manifests with count mismatch",
        )
    )

    # 2) Empty title/description rates from merged records
    merged_total = 0
    empty_title = 0
    empty_desc = 0
    if config.merged_records_path.exists():
        with open(config.merged_records_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                merged_total += 1
                if not str(row.get("title", "")).strip():
                    empty_title += 1
                if not str(row.get("description", "")).strip():
                    empty_desc += 1

    title_pct = (100.0 * empty_title / merged_total) if merged_total else 0.0
    desc_pct = (100.0 * empty_desc / merged_total) if merged_total else 0.0
    metrics["merged_total"] = merged_total
    metrics["empty_title_pct"] = round(title_pct, 3)
    metrics["empty_description_pct"] = round(desc_pct, 3)

    checks.append(QCCheck(name="empty_title_pct", passed=title_pct <= 5.0, value=title_pct, threshold=5.0))
    checks.append(QCCheck(name="empty_description_pct", passed=desc_pct <= 60.0, value=desc_pct, threshold=60.0))

    # 3) Sample URL reachability (from distributions table if exists)
    reachable = 0
    checked = 0
    if config.db_path.exists():
        con = duckdb.connect(str(config.db_path), read_only=True)
        try:
            rows = con.execute(
                "SELECT url FROM ds_distributions WHERE url IS NOT NULL AND url != '' LIMIT 200"
            ).fetchall()
        finally:
            con.close()

        urls = [str(r[0]) for r in rows if isinstance(r[0], str) and r[0].startswith(("http://", "https://"))]
        random.seed(42)
        sample = random.sample(urls, k=min(20, len(urls))) if urls else []
        for url in sample:
            checked += 1
            try:
                req = urllib.request.Request(url, method="HEAD")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if int(resp.status) < 500:
                        reachable += 1
            except Exception:
                pass

    reach_pct = (100.0 * reachable / checked) if checked else 100.0
    metrics["url_sample_checked"] = checked
    metrics["url_sample_reachable_pct"] = round(reach_pct, 3)
    checks.append(
        QCCheck(
            name="url_sample_reachability_pct",
            passed=reach_pct >= 70.0,
            value=reach_pct,
            threshold=70.0,
            severity="warning" if checked == 0 else "critical",
        )
    )

    report = QCReport(scope="datasets", checks=checks, metrics=metrics)
    write_qc_report(config.qc_report_path, report)
    write_stage_manifest(
        manifest_path=config.manifests_dir / "qc.json",
        stage="qc",
        status="ok" if report.passed else "failed",
        metrics={"passed": report.passed, **metrics},
        artifacts=[config.qc_report_path],
        started_at=started_at,
    )
    evaluate_fail_fast(report, fail_fast=config.fail_fast_qc if fail_fast is None else fail_fast)
    return report
