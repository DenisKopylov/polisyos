"""Public native factory fault followed by a separate-process public resume."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_WRITE_SCRIPT = r"""
import hashlib, json, sys
from pathlib import Path
from polisyos.core.canon.canon_json import from_canonical_bytes
from polisyos.scientist.methods.search.controller import SearchStatus
from test_service_persistence import _runner

root, failure = Path(sys.argv[1]), sys.argv[2]
runner, store, _, suite, evaluator, spec = _runner(root)
service = runner.create_service(spec, suite_ref=suite, max_iterations=3)
actual_put, actual_read = store.put_json, store.get_verified_snapshot
fault = {"count": 0, "readback_ref": None, "proposal": None}
acknowledged = {}

def checkpoint_put(payload, options, **kwargs):
    is_checkpoint = options.kind == "scientist.search.service_checkpoint"
    if (is_checkpoint and payload.ask_iteration == 2
        and payload.pending_candidate_ids == ["candidate_1_0"] and fault["count"] == 0):
        fault["count"] += 1
        fault["proposal"] = payload.pending_candidates["candidate_1_0"]
        if failure == "write":
            raise OSError("actual factory checkpoint write fault")
        ref = actual_put(payload, options, **kwargs)
        fault["readback_ref"] = ref
        return ref
    ref = actual_put(payload, options, **kwargs)
    if (is_checkpoint and payload.completed_candidate_ids == ["candidate_0_0"]
        and not payload.pending_candidate_ids and payload.failure is None):
        acknowledged["ref"] = ref
        acknowledged["bytes"] = store.get_bytes(ref)
    return ref

def checkpoint_read(ref):
    snapshot = actual_read(ref)
    if fault["readback_ref"] == ref:
        fault["readback_ref"] = None
        raise OSError("actual factory checkpoint readback fault")
    return snapshot

store.put_json, store.get_verified_snapshot = checkpoint_put, checkpoint_read
try:
    service.run_search(initial_context={})
except OSError as exc:
    assert str(exc) == f"actual factory checkpoint {failure} fault"
else:
    raise AssertionError("configured public factory never reached the actual CAS fault")
assert fault["count"] == 1
assert evaluator.calls == [1]
assert fault["proposal"]["value"] == 2
assert service.controller._status is SearchStatus.FAILED
assert service.controller._generator.get_state()["index"] == 1
assert service._ask_iteration == 1
assert service._pending_candidates == {}
assert service._completed_candidate_ids == {"candidate_0_0"}
assert [row.candidate["value"] for row in service.controller._history] == [1]
assert service.controller._run_state.evaluation_iterations == 1
assert service.controller._run_state.stage_b_evaluations == 1
assert store.get_bytes(acknowledged["ref"]) == acknowledged["bytes"]
failed_ref = service.checkpoint_ref
failed_bytes = store.get_bytes(failed_ref)
saved = from_canonical_bytes(failed_bytes)
assert saved["failure"] == f"OSError: actual factory checkpoint {failure} fault"
assert saved["pending_candidate_ids"] == []
assert saved["generator_state"]["index"] == saved["ask_iteration"] == 1
assert saved["run_state"]["status"] == "failed"
assert saved["configuration"]["replay_profile"]["version"] == "native-autotune-replay.v2"

# Check the physical live proposal too: a saved cursor marker cannot stand in
# for actually restored generator behavior after the composed loop failure.
live_next = service.ask(None, None, {})[0]
assert live_next.candidate_id == "candidate_1_0"
assert live_next.payload == fault["proposal"], {"live": live_next.payload, "expected": fault["proposal"]}

# Exercise the intended next subject through a newly configured public factory.
fresh_runner, _, _, _, _, fresh_spec = _runner(root)
fresh = fresh_runner.create_service(fresh_spec, suite_ref=suite, max_iterations=3)
fresh.restore(failed_ref)
next_proposal = fresh.ask(None, None, {})[0]
assert next_proposal.candidate_id == "candidate_1_0"
assert next_proposal.payload == fault["proposal"]
assert next_proposal == live_next
origins = {}
for name in ("polisyos.scientist.methods.autotune.runtime",
             "polisyos.scientist.methods.search.service",
             "polisyos.scientist.methods.search.controller", "test_service_persistence"):
    path = Path(sys.modules[name].__file__).resolve()
    origins[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
print("FACTORY_WRITE_RECEIPT:" + json.dumps({
    "fault": failure, "fault_count": fault["count"],
    "suite_ref": suite.model_dump(mode="json"),
    "failed_ref": failed_ref.model_dump(mode="json"),
    "failed_bytes_sha256": hashlib.sha256(failed_bytes).hexdigest(),
    "acknowledged_ref": acknowledged["ref"].model_dump(mode="json"),
    "acknowledged_bytes_sha256": hashlib.sha256(acknowledged["bytes"]).hexdigest(),
    "search_id": service.controller._run_state.search_id,
    "next_proposal": next_proposal.model_dump(mode="json"),
    "origins": origins, "python": sys.version, "executable": sys.executable,
}))
"""


_READ_SCRIPT = r"""
import hashlib, json, sys
from pathlib import Path
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation, load_model_artifact
from polisyos.scientist.methods.search.controller import SearchStatus
from test_service_persistence import _runner

root, prior = Path(sys.argv[1]), json.loads(sys.argv[2])
runner, _, registry, _, evaluator, spec = _runner(root)
suite, failed_ref = (ArtifactRef.model_validate(prior[key]) for key in ("suite_ref", "failed_ref"))
result = runner.resume(spec, suite_ref=suite, checkpoint_ref=failed_ref, max_iterations=3)
assert [row.candidate["value"] for row in result.history] == [1, 2, 3]
assert evaluator.calls == [2, 1, 3, 2]
assert result.iterations_completed == result.stage_b_evaluations == 3
assert result.best_candidate["value"] == 3
assert registry.get("resume").metrics == {"score": 3.0}
assert result.search_id == prior["search_id"]
assert result.stopping_reason == "Maximum iterations (3) reached"
reopened_store = FileSystemCAS(root / "cas")
assert hashlib.sha256(reopened_store.get_bytes(failed_ref)).hexdigest() == prior["failed_bytes_sha256"]
assert hashlib.sha256(reopened_store.get_bytes(ArtifactRef.model_validate(prior["acknowledged_ref"]))).hexdigest() == prior["acknowledged_bytes_sha256"]
final_ref = ArtifactRef.model_validate(result.telemetry["checkpoint_ref"])
observer_runner, _, _, _, _, observer_spec = _runner(root)
observer = observer_runner.create_service(observer_spec, suite_ref=suite, max_iterations=3)
observer.restore(final_ref)
assert observer.controller._status is SearchStatus.STOPPED
assert observer._pending_candidates == {}
assert observer._completed_candidate_ids == {"candidate_0_0", "candidate_1_0", "candidate_2_0"}
assert observer.controller._generator.get_state()["index"] == observer._ask_iteration == 3
assert observer.controller._run_state.pareto_front == result.pareto_front
assert len(result.pareto_front) == 1
frontier = result.pareto_front[0]
assert frontier["candidate"] == result.best_candidate
assert frontier["objectives"] == [{"name": "score", "raw_value": -3.0, "direction": "minimize"}]
assert frontier["candidate_hash"] == result.history[-1].stage_b_result["simulation_results"]["candidate_artifact_ref"]["artifact_id"]
for row in observer.controller._history:
    ref = ArtifactRef.model_validate(row.stage_b_result["simulation_results"]["evaluation_artifact_ref"])
    evaluation = load_model_artifact(reopened_store, ref, BenchmarkEvaluation)
    assert evaluation.holdout_metrics == {"score": float(row.candidate["value"])}
origins = {}
for name in ("polisyos.scientist.methods.autotune.runtime",
             "polisyos.scientist.methods.search.service",
             "polisyos.scientist.methods.search.controller", "test_service_persistence"):
    path = Path(sys.modules[name].__file__).resolve()
    origins[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
assert origins == prior["origins"]
print("FACTORY_RESUME_RECEIPT:" + json.dumps({
    "history_values": [row.candidate["value"] for row in result.history],
    "calls": evaluator.calls, "iterations": result.iterations_completed,
    "stage_b": result.stage_b_evaluations, "stopping_reason": result.stopping_reason,
    "best": result.best_candidate, "champion": registry.get("resume").metrics,
    "checkpoint_ref": result.telemetry["checkpoint_ref"], "search_id": result.search_id,
    "origins": origins,
}))
"""


def _process(script, tmp_path, *arguments):
    # Both processes load the same tracked helper/model/evaluator profile.
    # They run in sequence because the reader depends on the writer's CAS refs.
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(Path(__file__).parent), environment.get("PYTHONPATH", "")])
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), *arguments],
        capture_output=True,
        text=True,
        env=environment,
    )
    print(
        json.dumps(
            {
                "child_stdout": result.stdout,
                "child_stderr": result.stderr,
                "child_returncode": result.returncode,
            },
            sort_keys=True,
        )
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def _receipt(result, prefix):
    line = next(line for line in result.stdout.splitlines() if line.startswith(prefix))
    return json.loads(line.removeprefix(prefix))


@pytest.mark.parametrize("failure", ["write", "readback"])
def test_public_factory_checkpoint_fault_fresh_process_resume_preserves_next_subject(
    tmp_path, failure
):
    writer = _process(_WRITE_SCRIPT, tmp_path, failure)
    written = _receipt(writer, "FACTORY_WRITE_RECEIPT:")
    reader = _process(_READ_SCRIPT, tmp_path, json.dumps(written))
    resumed = _receipt(reader, "FACTORY_RESUME_RECEIPT:")
    assert written["fault"] == failure
    assert written["fault_count"] == 1
    assert resumed["history_values"] == [1, 2, 3]
    assert resumed["search_id"] == written["search_id"]
    print(
        json.dumps(
            {
                "failure": failure,
                "writer_stdout": writer.stdout,
                "reader_stdout": reader.stdout,
                "writer_stderr": writer.stderr,
                "reader_stderr": reader.stderr,
            },
            sort_keys=True,
        )
    )
