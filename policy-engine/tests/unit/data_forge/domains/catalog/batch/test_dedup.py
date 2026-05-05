from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
from polisyos.data_forge.domains.catalog.batch.dedup import merge_and_dedup
from polisyos.data_forge.domains.catalog.knowledge.types import DatasetRecord

if TYPE_CHECKING:
    from pathlib import Path


def _write_jsonl(path: Path, rows: list[DatasetRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(row.model_dump_json() + "\n")


def test_merge_and_dedup_uses_source_agency_dataset_key(tmp_path) -> None:
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snap")

    duplicate_key = "oecd|OECD.TEST|DF_1"
    first = DatasetRecord(
        id="a",
        title="First",
        source="oecd",
        agency="OECD.TEST",
        dataset_id="DF_1",
        dedup_key=duplicate_key,
    )
    second = DatasetRecord(
        id="b",
        title="Second",
        source="oecd",
        agency="OECD.TEST",
        dataset_id="DF_1",
        dedup_key=duplicate_key,
    )
    third = DatasetRecord(
        id="c",
        title="Third",
        source="imf",
        agency="IMF",
        dataset_id="IFS",
        dedup_key="imf|IMF|IFS",
    )

    _write_jsonl(config.normalized_dir / "oecd.jsonl", [first, second])
    _write_jsonl(config.normalized_dir / "imf.jsonl", [third])

    stats = merge_and_dedup(config)

    assert stats["merged_records"] == 2
    assert stats["duplicates"] == 1
    assert config.merged_records_path.exists()
    assert config.duplicates_report_path.exists()

    lines = config.merged_records_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
