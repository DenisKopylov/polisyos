"""Run only after J release: retain actual recorded admission, remove its replay."""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
NODE = "tests/unit/runtime/quality/workspace/test_production_case_proof_custody.py::test_recorded_refusal_capsule_requires_complete_actual_recomputation"


class RemoveRecordedRecomputation:
    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item):
        from polisyos.runtime.quality.workspace import loop
        from tools.quality.validation import check_layer3_gy_loop_artifacts as owner

        if item.nodeid != NODE:
            yield
            return
        old, _, _ = item.funcargs["actual_j_family_pair"]
        payload = old._frozen_final_output()
        packet, store, _ = owner._restore_j_recorded_evidence(
            outcome=payload[owner.OUTCOME_RUN_PATH],
            replay_artifact=payload[owner.OUTCOME_REPLAY_PATH],
            repo_root=ROOT,
        )
        real = loop.resolve_production_case_admission
        retained = real(
            store=store,
            receipt_ref=packet["admission_ref"],
            request_ref=packet["request_ref"],
            catalog=item.funcargs["actual_j_catalog"],
            repo_root=ROOT,
        )
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(loop, "resolve_production_case_admission", lambda **kwargs: retained)
            yield


if __name__ == "__main__":
    raise SystemExit(pytest.main(["-q", "-rA", "--show-capture=no", "--tb=short", NODE], plugins=[RemoveRecordedRecomputation()]))
