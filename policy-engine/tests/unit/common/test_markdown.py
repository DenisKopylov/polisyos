"""Behavioral vectors for source-preserving Markdown table tokenization."""

import importlib
import json
from pathlib import Path

import pytest

VECTORS = json.loads(
    (Path(__file__).resolve().parents[2] / "fixtures/common/markdown_table_rows.json").read_text()
)["rows"]


@pytest.mark.parametrize("vector", VECTORS, ids=lambda vector: vector["name"])
def test_split_markdown_table_row_preserves_source_cells(vector: dict[str, object]) -> None:
    """Raw splitting or stripping source cells must break these literal expectations."""
    try:
        owner = importlib.import_module("polisyos.common.markdown")
    except ModuleNotFoundError:
        pytest.fail("source-preserving Markdown table tokenizer is absent")
    assert owner.split_markdown_table_row(vector["text"]) == vector["cells"]
