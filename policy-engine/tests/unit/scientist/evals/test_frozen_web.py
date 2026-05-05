from __future__ import annotations

import pytest
from polisyos.scientist.evals.frozen_web import FrozenWebHarnessConfig, FrozenWebPack, FrozenWebTask


def test_frozen_web_harness_rejects_live_web() -> None:
    with pytest.raises(ValueError, match="must not use live web"):
        FrozenWebHarnessConfig(allow_live_web=True)


def test_frozen_web_pack_validates_expected_sources() -> None:
    with pytest.raises(ValueError, match="unknown documents"):
        FrozenWebPack(
            pack_id="pack",
            revision="1",
            tasks=[FrozenWebTask(task_id="task", question="q", expected_source_ids=["missing"])],
        )
