"""Exercise runtime consumers of the core wheels and optional HNSW backend."""

from __future__ import annotations

import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

import pytest


class DependencyRuntimeTests(unittest.TestCase):
    def test_tokenizer_regex_matches_and_rejects_special_tokens(self) -> None:
        import tiktoken

        from polisyos.scientist.orchestration.llm.token_estimator import _tiktoken_count

        corpus = (
            "Policy budgets: 123,456.78 and -42%.",
            "Політика — дані, дія, наслідок. Україна 🇺🇦",
            "中文政策 العربية हिन्दी",
            "a\u0301 é 👩🏽‍💻\n\t  multiple   spaces\r\n",
            "<|endoftext> is a near miss; (a+b)[x]? is literal.",
        )
        for name in sorted(tiktoken.list_encoding_names()):
            encoding = tiktoken.get_encoding(name)
            for text in corpus:
                # This library consumer uses Python regex for segmentation;
                # the ordinary encoder provides an independent Rust path.
                actual = encoding._encode_only_native_bpe(text)
                assert actual == encoding.encode_ordinary(text)
                assert encoding.decode(actual) == text
            for token in sorted(encoding.special_tokens_set):
                # The normal encode path consumes Python regex here, before
                # Rust encoding can admit a forbidden special token.
                with pytest.raises(ValueError) as error:
                    encoding.encode(f"policy {token} consequence")
                assert token in str(error.value)
                assert encoding.encode(token, allowed_special="all") == [
                    encoding._special_tokens[token]
                ]
        encoding = tiktoken.get_encoding("cl100k_base")
        for text in corpus:
            assert _tiktoken_count(text, model=None) == len(encoding.encode(text))
        for token in sorted(encoding.special_tokens_set):
            with pytest.raises(ValueError) as error:
                _tiktoken_count(token, model=None)
            assert token in str(error.value)

    def test_ckan_reads_real_ods_and_enforces_limits(self) -> None:
        import pandas as pd

        from polisyos.fabric.connectors.sources.ckan_resource import CKANResourceConnector
        from polisyos.fabric.connectors.types import FetchError

        sheets = {
            "Доходи": pd.DataFrame(
                {"region": ["Київ", "Львів"], "amount": [1234.5, -7.25], "approved": [True, False]}
            ),
            "Costs": pd.DataFrame({"region": ["Одеса"], "amount": [0.0], "approved": [True]}),
        }
        payload = io.BytesIO()
        with pd.ExcelWriter(payload, engine="odf") as writer:
            for name, frame in sheets.items():
                frame.to_excel(writer, sheet_name=name, index=False)
        expected = pd.concat(
            [frame.assign(__sheet_name=name) for name, frame in sheets.items()], ignore_index=True
        )
        actual = CKANResourceConnector._parse_resource(payload.getvalue(), "ods", max_rows=3)
        pd.testing.assert_frame_equal(actual, expected)
        for raw, limit, cause in (
            (payload.getvalue(), 2, "row limit"),
            (b"not an ODS ZIP", 3, "Failed to parse ODS resource"),
        ):
            with pytest.raises(FetchError) as error:
                CKANResourceConnector._parse_resource(raw, "ods", max_rows=limit)
            assert cause.lower() in str(error.value).lower()

    @unittest.skipUnless(importlib.util.find_spec("hnswlib"), "requires vector-search extra")
    def test_vector_search_updates_and_roundtrips_through_cas(self) -> None:
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.scientist.agent.vector_memory import VectorMemoryStore

        memory = VectorMemoryStore(dim=3, max_elements=20)
        memory.add("north", [1.0, 0.0, 0.0], {"source": "north"})
        memory.add("east", [0.0, 1.0, 0.0], {"source": "east"})
        memory.add("south", [-1.0, 0.0, 0.0], {"source": "south"})
        first = memory.query([1.0, 0.0, 0.0], top_k=3)
        assert [row[0] for row in first] == ["north", "east", "south"]
        assert [round(row[1], 5) for row in first] == [0.0, 1.0, 2.0]
        assert first[0][2] == {"source": "north"}
        memory.add("east", [1.0, 1.0, 0.0], {"source": "updated"})
        assert len(memory) == 3
        updated = memory.query([1.0, 1.0, 0.0], top_k=1)
        assert updated[0][0] == "east"
        assert updated[0][1] == pytest.approx(0.0, abs=1e-5)
        assert updated[0][2] == {"source": "updated"}
        with tempfile.TemporaryDirectory() as temp:
            cas = FileSystemCAS(Path(temp))
            reference = memory.save_to_artifact(cas)
            restored = VectorMemoryStore(dim=3, max_elements=20)
            restored.load_from_artifact(cas, reference)
            assert restored.query([1.0, 0.0, 0.0], top_k=3) == memory.query(
                [1.0, 0.0, 0.0], top_k=3
            )
            assert len(restored) == 3
