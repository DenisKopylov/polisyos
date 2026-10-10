from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.data_forge.domains.academic.batch import _resolve_extract_io as io
from polisyos.data_forge.domains.academic.batch import resolve_extract as facade

_KEYED_LOADERS = (io._load_jsonl_keyed, io._load_jsonl_lazy, io._load_jsonl_grouped)


def test_resolve_extract_io_helpers_are_reexported() -> None:
    assert io._terminal_state("published") is True
    assert facade._retryable_state("retryable_failed") is True


@pytest.mark.parametrize("loader", _KEYED_LOADERS, ids=["keyed", "lazy", "grouped"])
@pytest.mark.parametrize(
    ("raw", "message"),
    [
        pytest.param(b"[]\n", "must be an object", id="valid-json-non-object"),
        pytest.param(b'{"title":"unkeyed"}\n', "no non-empty 'work_id'", id="missing-key"),
        pytest.param(b"{not-json}\n", "Malformed JSONL record", id="malformed-json"),
        pytest.param(b"\xff\n", "Malformed JSONL record", id="invalid-utf8"),
    ],
)
def test_keyed_jsonl_loaders_reject_present_bad_rows_without_mutation(
    loader,
    raw: bytes,
    message: str,
    tmp_path: Path,
) -> None:
    path = tmp_path / "records.jsonl"
    path.write_bytes(raw)

    with pytest.raises(ValueError, match=message):
        loader(path)

    assert path.read_bytes() == raw


def test_keyed_jsonl_loaders_distinguish_absence_and_blank_lines(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.jsonl"
    blank_path = tmp_path / "blank.jsonl"
    blank_path.write_bytes(b"\n  \t\n")
    sentinel = object()

    for loader in _KEYED_LOADERS:
        for path in (missing_path, blank_path):
            loaded = loader(path)
            if isinstance(loaded, io._LazyJsonlDict):
                assert loaded.get("missing", sentinel) is sentinel
                assert "missing" not in loaded
            else:
                assert loaded == {}


def test_keyed_jsonl_loader_uses_exact_caller_key_without_aliases(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    path.write_text('{"work_id":"W1","value":1}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="no non-empty 'record_id'"):
        io._load_jsonl_keyed(path, key="record_id")


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        pytest.param(b'{"work_id":"selected","text":\n', "Malformed JSONL", id="syntax"),
        pytest.param(b"[]\n", "must be an object", id="non-object"),
        pytest.param(b'{"text":"cached"}\n', "no non-empty 'work_id'", id="missing-key"),
        pytest.param(
            b'{"work_id":"other","text":"changed"}\n',
            "no longer matches key",
            id="changed-key",
        ),
    ],
)
def test_lazy_jsonl_get_and_pop_propagate_corruption_without_mutating_raw(
    replacement: bytes,
    message: str,
    tmp_path: Path,
) -> None:
    path = tmp_path / "fulltext.jsonl"
    path.write_bytes(b'{"work_id":"selected","text":"cached"}\n')
    records = io._load_jsonl_lazy(path)
    assert records.get("selected") == {"work_id": "selected", "text": "cached"}

    path.write_bytes(replacement)
    corrupted_bytes = path.read_bytes()
    fallback = {"work_id": "fallback"}
    with pytest.raises(ValueError, match=message):
        records.get("selected", fallback)
    with pytest.raises(ValueError, match=message):
        records.pop("selected", fallback)

    assert path.read_bytes() == corrupted_bytes
    assert "selected" in records
    assert records.get("missing", fallback) is fallback
    assert records.pop("missing", fallback) is fallback


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param(b"[]\n", id="valid-json-non-object"),
        pytest.param(b"{not-json}\n", id="malformed-json"),
        pytest.param(b"\xff\n", id="invalid-utf8"),
    ],
)
def test_offset_jsonl_reader_rejects_malformed_complete_rows_without_mutation(
    raw: bytes, tmp_path: Path
) -> None:
    path = tmp_path / "completed-queue.jsonl"
    path.write_bytes(raw)

    with pytest.raises(ValueError):
        io._load_jsonl_from_offset(path, 0)

    assert path.read_bytes() == raw


def test_offset_jsonl_reader_does_not_invent_a_work_id_key(tmp_path: Path) -> None:
    path = tmp_path / "completed-queue.jsonl"
    path.write_bytes(b'{"result":"ready"}\n')

    rows, next_offset = io._load_jsonl_from_offset(path, 0)

    assert rows == [{"result": "ready"}]
    assert next_offset == path.stat().st_size


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        pytest.param(b"[]\n", "must be an object", id="non-object"),
        pytest.param(b'{"value":1}\n', "cache_key", id="missing-exact-key"),
        pytest.param(b"{bad json}\n", "Malformed JSONL", id="malformed-json"),
        pytest.param(b"\xff\n", "Malformed JSONL", id="invalid-utf8"),
    ],
)
def test_metadata_cache_rejects_malformed_present_rows_without_mutation(
    raw: bytes, message: str, tmp_path: Path
) -> None:
    path = tmp_path / "metadata-cache.jsonl"
    path.write_bytes(raw)

    with pytest.raises(ValueError, match=message):
        io._load_metadata_cache(path)

    assert path.read_bytes() == raw


def test_metadata_cache_keeps_absence_and_blank_lines_empty(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing-metadata.jsonl"
    blank_path = tmp_path / "blank-metadata.jsonl"
    blank_path.write_bytes(b"\n  \t\n")

    assert io._load_metadata_cache(missing_path) == {}
    assert io._load_metadata_cache(blank_path) == {}


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        pytest.param(b"[]\n", "must be an object", id="non-object"),
        pytest.param(b'{"retry_count":1}\n', "work_id", id="missing-exact-key"),
        pytest.param(b"{bad json}\n", "Malformed JSONL", id="malformed-json"),
        pytest.param(b"\xff\n", "Malformed JSONL", id="invalid-utf8"),
    ],
)
def test_retry_queue_read_modify_write_refuses_bad_rows_before_rewrite(
    raw: bytes, message: str, tmp_path: Path
) -> None:
    from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig

    config = AcademicBatchConfig(snapshot_root=tmp_path / "snapshot")
    config.timeout_retry_queue_path.parent.mkdir(parents=True, exist_ok=True)
    config.timeout_retry_queue_path.write_bytes(raw)

    with pytest.raises(ValueError, match=message):
        io._persist_timeout_retry_queue(config, {"items": {}})

    assert config.timeout_retry_queue_path.read_bytes() == raw


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        pytest.param(b"", "Malformed progress JSON document", id="blank-present"),
        pytest.param(b"{bad json}", "Malformed progress JSON document", id="malformed"),
        pytest.param(b"\xff", "Malformed progress JSON document", id="invalid-utf8"),
        pytest.param(b"[]", "must be an object", id="non-object"),
        pytest.param(b'{"version":1}', "items object", id="missing-items"),
        pytest.param(b'{"items":[]}', "items object", id="wrong-items-shape"),
        pytest.param(
            b'{"items":{"W-not-selected":[]}}',
            "non-object item",
            id="non-object-unselected-work-entry",
        ),
    ],
)
def test_progress_reader_refuses_present_malformed_documents_without_rewrite(
    raw: bytes, message: str, tmp_path: Path
) -> None:
    path = tmp_path / "progress.json"
    path.write_bytes(raw)

    with pytest.raises(ValueError, match=message):
        io._load_progress(path)

    assert path.read_bytes() == raw


def test_progress_reader_keeps_only_missing_file_as_empty_default(tmp_path: Path) -> None:
    path = tmp_path / "missing-progress.json"

    assert io._load_progress(path) == {"version": 1, "updated_at": "", "items": {}}
