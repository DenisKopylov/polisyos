from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.run.context import RunContext


@pytest.fixture
def mock_store():
    store = MagicMock()
    _fake_sha = "sha256:" + "a1" * 32
    store.put_json.return_value = ArtifactRef(
        artifact_id=_fake_sha,
        media_type="application/json",
        kind="test",
    )
    return store


@pytest.fixture
def mock_run_context(mock_store):
    ctx = MagicMock(spec=RunContext)
    ctx.store = mock_store
    ctx.emit = MagicMock()
    return ctx
