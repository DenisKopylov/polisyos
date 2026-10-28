"""Behavioral controls for the shared Foundry numeric NPZ decoder."""

from __future__ import annotations

import io
import zipfile

import numpy as np
import pytest

from polisyos.foundry.execute import BoundedNumericNPZError, read_numeric_npz_bounded


def _npz(value: np.ndarray) -> bytes:
    stream = io.BytesIO()
    np.savez(stream, vectors=value)
    return stream.getvalue()


def _read(data: bytes, *, ndim: int = 2, allow_empty: bool = False) -> tuple[np.ndarray, ...]:
    return read_numeric_npz_bounded(
        data,
        names=("vectors",),
        max_entries=1,
        max_elements=100,
        max_member_bytes=4096,
        ndim=ndim,
        allow_empty=allow_empty,
        exact_dtype="<f4" if ndim == 2 else None,
    )


def test_bounded_matrix_and_existing_1d_numeric_paths() -> None:
    matrix = np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype="<f4")
    (result,) = _read(_npz(matrix))
    assert result.shape == (2, 2)
    np.testing.assert_array_equal(result, matrix)
    assert not result.flags.writeable
    (vector,) = _read(_npz(np.asarray([1, 2], dtype=np.int32)), ndim=1)
    np.testing.assert_array_equal(vector, [1, 2])


def test_empty_matrix_is_only_admitted_explicitly() -> None:
    data = _npz(np.empty((0, 2), dtype="<f4"))
    with pytest.raises(BoundedNumericNPZError, match="shape_or_byte_limit"):
        _read(data)
    assert _read(data, allow_empty=True)[0].shape == (0, 2)


@pytest.mark.parametrize(
    "value",
    [
        np.asarray([[object()]], dtype=object),
        np.asarray([[1.0]], dtype=np.float64),
        np.asarray([[float("nan")]], dtype=np.float32),
        np.asarray([1.0, 2.0], dtype=np.float32),
        np.empty((1, 0), dtype=np.float32),
    ],
)
def test_wrong_dtype_shape_and_nonfinite_are_refused(value: np.ndarray) -> None:
    with pytest.raises(BoundedNumericNPZError):
        _read(_npz(value), allow_empty=True)


def test_duplicate_names_and_compressed_members_refuse_before_inflation() -> None:
    data = _npz(np.asarray([[1.0]], dtype="<f4"))
    stream = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(stream, "w") as dst:
        member = src.read("vectors.npy")
        dst.writestr("vectors.npy", member)
        with pytest.warns(UserWarning, match="Duplicate name"):
            dst.writestr("vectors.npy", member)
    with pytest.raises(BoundedNumericNPZError, match="entry_limit|inventory"):
        _read(stream.getvalue())
    compressed = io.BytesIO()
    np.savez_compressed(compressed, vectors=np.asarray([[1.0]], dtype="<f4"))
    with pytest.raises(BoundedNumericNPZError, match="codec_or_size"):
        _read(compressed.getvalue())


def test_source_and_element_limits_fail_closed() -> None:
    data = _npz(np.ones((2, 2), dtype="<f4"))
    with pytest.raises(BoundedNumericNPZError, match="entry_codec_or_size"):
        read_numeric_npz_bounded(
            data, names=("vectors",), max_entries=1, max_elements=100, max_member_bytes=8, ndim=2
        )
    with pytest.raises(BoundedNumericNPZError, match="shape_or_byte_limit"):
        read_numeric_npz_bounded(
            data, names=("vectors",), max_entries=1, max_elements=3, max_member_bytes=4096, ndim=2
        )


def test_forged_zip_entry_count_refuses_before_zipfile_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import struct

    import polisyos.foundry.execute._internal.snapshots as owner

    source = io.BytesIO()
    np.savez(source, vectors=np.ones((1, 1), dtype="<f4"), extra=np.ones((1, 1), dtype="<f4"))
    data = bytearray(source.getvalue())
    eocd = data.rfind(b"PK\x05\x06")
    assert eocd >= 0
    struct.pack_into("<H", data, eocd + 8, 1)
    struct.pack_into("<H", data, eocd + 10, 1)

    def forbid_reader(*_args: object, **_kwargs: object) -> None:
        pytest.fail("central directory must be bounded before ZipFile construction")

    monkeypatch.setattr(owner, "ZipFile", forbid_reader)
    with pytest.raises(BoundedNumericNPZError, match="entry_limit"):
        _read(bytes(data))


def _unpickle_marker(path: str) -> int:
    from pathlib import Path

    Path(path).write_text("executed")
    return 1


class _UnsafePickle:
    def __init__(self, path: str) -> None:
        self.path = path

    def __reduce__(self):
        return _unpickle_marker, (self.path,)


def test_untrusted_object_npz_never_executes_pickle_callback(tmp_path) -> None:
    marker = tmp_path / "unpickled"
    data = _npz(np.asarray([[_UnsafePickle(str(marker))]], dtype=object))
    refused = False
    try:
        _read(data)
    except BoundedNumericNPZError:
        refused = True
    assert not marker.exists(), "untrusted NPZ executed a pickle callback"
    assert refused
