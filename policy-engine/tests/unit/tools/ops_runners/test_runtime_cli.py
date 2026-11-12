"""Runtime CLI forwards source-only replay preflight without numerical work."""

import json
import os
from pathlib import Path
from types import SimpleNamespace

from polisyos.runtime.quality import n5_replay_execution as replay
from tests.unit.runtime.quality.test_n5_replay_execution import _spec
from tools.ops_runners import runtime_cli


def test_replay_profile_preflight_dispatch_sets_assigned_environment(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    action = replay.N5ReplayNativePreflightAction(launch_spec=_spec(), cas_root=str(tmp_path))
    action_path = tmp_path / "action.json"
    action_path.write_text(action.model_dump_json(), encoding="utf-8")
    seen = []

    def observe(value):
        seen.append(
            (value, os.environ.get("POLISYOS_STRICT"), os.environ.get("FOUNDRY_SHAPE_CHECK"))
        )
        return SimpleNamespace(model_dump_json=lambda: json.dumps({"observed": True}))

    monkeypatch.setattr(replay, "observe_n5_replay_native_preflight", observe)
    assert (
        runtime_cli.main(["scientist", "n5-replay-profile-preflight", "--action", str(action_path)])
        == 0
    )
    assert seen == [(action, "1", "0")]
    assert replay._worker_result_payload(capsys.readouterr().out) == '{"observed": true}'
