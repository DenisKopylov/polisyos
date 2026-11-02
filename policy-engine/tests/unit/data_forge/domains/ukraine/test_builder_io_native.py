"""Native domain serialization and actual atomic-writer failure phases."""

from __future__ import annotations

import os
import stat
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydantic import BaseModel, ConfigDict

from polisyos.data_forge.domains.ukraine.builders import io
from polisyos.data_forge.domains.ukraine.models import build_default_pipeline_config
from polisyos.data_forge.kernel.io import atomic


class _ExampleDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int


@pytest.mark.parametrize("proxy", ["absent", "empty"])
def test_native_procurement_fallback_preserves_warning_and_required_source(
    tmp_path: Path, proxy: str
) -> None:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    proxy_source = config.sources["spending_contracts_procurement_proxy"]
    proxy_path = (
        config.build_root.normalized_dir / proxy_source.source_id / proxy_source.normalized_artifact
    )
    if proxy == "empty":
        proxy_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"amount": pd.Series(dtype="float64")}).to_parquet(proxy_path, index=False)
    required = config.sources["prozorro_full"]
    required_path = (
        config.build_root.normalized_dir / required.source_id / required.normalized_artifact
    )
    required_path.parent.mkdir(parents=True, exist_ok=True)
    expected = pd.DataFrame({"amount": [10.0, 10.0], "row_id": ["first", "second"]})
    expected.to_parquet(required_path, index=False)
    before = required_path.read_bytes()
    frame, selected, warnings = io._select_procurement_frame(config)
    pd.testing.assert_frame_equal(frame, expected)
    assert selected == "prozorro_full"
    assert warnings == (
        ["procurement_source_empty:spending_contracts_procurement_proxy"]
        if proxy == "empty"
        else []
    ) + ["procurement_source_selected:prozorro_full"]
    assert required_path.read_bytes() == before
    missing = config.model_copy(deep=True)
    missing.sources["prozorro_full"].normalized_artifact = "not_available.parquet"
    with pytest.raises(FileNotFoundError, match="missing normalized artifact for prozorro_full"):
        io._select_procurement_frame(missing)


def test_domain_json_keeps_legacy_unicode_numpy_date_path_and_dto_bytes(tmp_path: Path) -> None:
    path = tmp_path / "payload.json"
    io._write_json(
        path,
        {
            "unicode": "Київ",
            "integer": np.int64(3),
            "array": np.asarray([1.5, 2.0]),
            "date": date(2024, 2, 29),
            "path": Path("fixture/é"),
            "dto": _ExampleDTO(value=7),
        },
    )
    assert path.read_bytes() == (
        b'{\n  "array": [\n    1.5,\n    2.0\n  ],\n  "date": "2024-02-29",\n'
        b'  "dto": {\n    "value": 7\n  },\n  "integer": 3,\n'
        b'  "path": "fixture/\\u00e9",\n'
        b'  "unicode": "\\u041a\\u0438\\u0457\\u0432"\n}'
    )


@pytest.mark.parametrize("format", ["json", "npz"])
@pytest.mark.parametrize("phase", ["write", "file_fsync", "replace", "directory_fsync"])
def test_actual_atomic_failure_distinguishes_before_and_after_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, format: str, phase: str
) -> None:
    target = tmp_path / f"payload.{format}"
    prior = b"previous target bytes"
    target.write_bytes(prior)
    real_fdopen, real_fsync, real_replace = os.fdopen, os.fsync, os.replace
    events: list[str] = []

    class _WriteRefusal:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            self.handle.__enter__()
            return self

        def __exit__(self, *args):
            return self.handle.__exit__(*args)

        def write(self, _payload):
            events.append("write")
            raise OSError("controlled write refusal")

    def fdopen(fd, *args, **kwargs):
        handle = real_fdopen(fd, *args, **kwargs)
        return _WriteRefusal(handle) if phase == "write" else handle

    def fsync(fd):
        kind = "directory_fsync" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file_fsync"
        events.append(kind)
        if phase == kind:
            raise OSError(f"controlled {kind} refusal")
        return real_fsync(fd)

    def replace(source, destination):
        events.append("replace")
        assert Path(destination) == target
        if phase == "replace":
            raise OSError("controlled replace refusal")
        return real_replace(source, destination)

    def write():
        if format == "json":
            return io._write_json(target, {"new": 7})
        return io._write_npz(target, weight=np.asarray([0.0, 2.5]), node_ids=np.asarray(["a", "b"]))

    with monkeypatch.context() as fault:
        fault.setattr(atomic.os, "fdopen", fdopen)
        fault.setattr(atomic.os, "fsync", fsync)
        fault.setattr(atomic.os, "replace", replace)
        with pytest.raises(OSError, match=f"controlled {phase} refusal"):
            write()
    assert events[-1] == phase
    assert list(tmp_path.glob(f".{target.name}.*.tmp")) == []
    if phase != "directory_fsync":
        assert target.read_bytes() == prior
    elif format == "json":
        assert target.read_bytes() == b'{\n  "new": 7\n}'
    else:
        with np.load(target, allow_pickle=False) as loaded:
            np.testing.assert_array_equal(loaded["weight"], [0.0, 2.5])
            np.testing.assert_array_equal(loaded["node_ids"], ["a", "b"])
    # A post-replace directory-fsync error leaves the new bytes visible. It
    # proves neither durability nor restoration of the previous target.
