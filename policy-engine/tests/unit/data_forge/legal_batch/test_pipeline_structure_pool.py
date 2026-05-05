from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING

from polisyos.data_forge.domains.legal.batch.config import BatchConfig
from polisyos.data_forge.domains.legal.batch.pipeline import _process_structure_chunk
from polisyos.data_forge.domains.legal.batch.progress import ProgressTracker
from polisyos.data_forge.domains.legal.batch.xml_parser import NPACard, NPADocument

if TYPE_CHECKING:
    from pathlib import Path


class _RaisingProcessPool:
    def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - invoked via monkeypatch
        raise PermissionError("SC_SEM_NSEMS_MAX unavailable")


def test_process_structure_chunk_falls_back_to_thread_pool(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = BatchConfig(
        cards_path=tmp_path / "cards.xml",
        texts_path=tmp_path / "texts.xml",
        output_dir=tmp_path / "lex",
        stages=frozenset({"structure"}),
        structure_workers=2,
    )
    config.output_dir.mkdir(parents=True, exist_ok=True)
    progress = ProgressTracker(config.progress_path)

    doc = NPADocument(
        card=NPACard(
            doc_id="deadbeefcafebabe",
            reestr_code="1",
            date_acc="2026-01-01",
            reestr_date="2026-01-02",
            status="чинний",
            doc_type="Наказ",
            name="Про затвердження додатка",
            publisher=("Міністерство",),
            number="1",
            publication=(),
            keywords=(),
            reg_date="2026-01-02",
            reg_number="1/1",
        ),
        text=("Додаток 1\nНайменування посад   Місячні посадові оклади\nРектор   300\n"),
    )

    monkeypatch.setattr(
        "polisyos.data_forge.domains.legal.batch.pipeline.ProcessPoolExecutor", _RaisingProcessPool
    )

    provisions_by_doc, total_provisions, stats = asyncio.run(
        _process_structure_chunk(
            config=config,
            progress=progress,
            docs_chunk=[doc],
        )
    )

    assert doc.card.doc_id in provisions_by_doc
    assert total_provisions == len(provisions_by_doc[doc.card.doc_id])
    assert total_provisions > 0
    assert stats.provision_docs_total == 1
    assert progress.is_done(doc.card.doc_id, "structured")
    provisions_path = config.provisions_dir / doc.card.doc_id[:2] / f"{doc.card.doc_id}.jsonl"
    assert provisions_path.exists()


def test_process_structure_chunk_uses_thread_pool_for_stdin_main(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = BatchConfig(
        cards_path=tmp_path / "cards.xml",
        texts_path=tmp_path / "texts.xml",
        output_dir=tmp_path / "lex-stdin",
        stages=frozenset({"structure"}),
        structure_workers=2,
    )
    config.output_dir.mkdir(parents=True, exist_ok=True)
    progress = ProgressTracker(config.progress_path)

    doc = NPADocument(
        card=NPACard(
            doc_id="feedfacecafefeed",
            reestr_code="2",
            date_acc="2026-01-01",
            reestr_date="2026-01-02",
            status="чинний",
            doc_type="Наказ",
            name="Про затвердження форми",
            publisher=("Міністерство",),
            number="2",
            publication=(),
            keywords=(),
            reg_date="2026-01-02",
            reg_number="2/2",
        ),
        text="Додаток 1\nТелефон            Телефакс                   Телекс\n",
    )

    monkeypatch.setattr(
        "polisyos.data_forge.domains.legal.batch.pipeline.ProcessPoolExecutor", _RaisingProcessPool
    )
    monkeypatch.setattr(sys.modules["__main__"], "__file__", "<stdin>", raising=False)

    provisions_by_doc, total_provisions, stats = asyncio.run(
        _process_structure_chunk(
            config=config,
            progress=progress,
            docs_chunk=[doc],
        )
    )

    assert doc.card.doc_id in provisions_by_doc
    assert total_provisions == len(provisions_by_doc[doc.card.doc_id])
    assert total_provisions > 0
    assert stats.provision_docs_total == 1
