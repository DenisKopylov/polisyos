from __future__ import annotations

from pathlib import Path

import pytest
from polisyos.fabric.connectors.transform.pipeline import TransformPipeline
from polisyos.fabric.ingestion import _load_transform_pipeline


def _write_transform_module(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from polisyos.fabric.connectors.transform.pipeline import TransformPipeline",
                "",
                "PIPELINE = TransformPipeline()",
            ]
        ),
        encoding="utf-8",
    )


def test_transform_dag_registry_allows_identity_pipeline() -> None:
    pipeline = _load_transform_pipeline("identity")
    assert isinstance(pipeline, TransformPipeline)


def test_transform_dag_rejects_untrusted_local_python_by_default(tmp_path: Path) -> None:
    transform_path = tmp_path / "local_transform.py"
    _write_transform_module(transform_path)

    with pytest.raises(ValueError, match="disabled by default"):
        _load_transform_pipeline(str(transform_path))


def test_transform_dag_trusted_local_flag_allows_local_python(tmp_path: Path) -> None:
    transform_path = tmp_path / "local_transform.py"
    _write_transform_module(transform_path)

    pipeline = _load_transform_pipeline(
        str(transform_path),
        allow_local_trust=True,
    )

    assert isinstance(pipeline, TransformPipeline)
