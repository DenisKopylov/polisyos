"""Bounded actual B CAS + existing D champion consumer profile.

Controlled existing evaluator inputs establish local technical behavior, not
appointment, production benchmark quality, or distributed publication rights.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.autotune.runtime import SearchLoopRunner

_ROOT = Path(os.environ["E02_CHAMPION_REPOSITORY"])
_OWNER_TEST = (
    _ROOT
    / "policy-engine/tests/unit/scientist/methods/autotune/test_champion_verified_snapshot.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "_existing_champion_owner_fixture", _OWNER_TEST
)
assert _SPEC is not None and _SPEC.loader is not None
_OWNER = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _OWNER
_SPEC.loader.exec_module(_OWNER)

_CHILD = r"""
import hashlib,json,os,sys
from contextlib import contextmanager
from pathlib import Path
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.autotune.models import PromotionPolicy
from polisyos.scientist.methods.autotune.registry import ChampionRegistry
root=Path(sys.argv[1]); packet=json.loads(Path(sys.argv[2]).read_text()); mode=sys.argv[3]
registry=ChampionRegistry(root/'champions',store=FileSystemCAS(root/'cas'))
before=registry._pointer_path('verified').read_bytes()
if mode == 'remove-lock':
    @contextmanager
    def guard_removed(loop_id):
        # Adversarial removal only: retain real CAS/basis/pointer effect but omit
        # the actual owner flock guard. This is never the positive profile.
        yield
    registry._promotion_lock=guard_removed
print(json.dumps({'phase':'ready_before_actual_consider','pid':os.getpid(),'mode':mode}),flush=True)
try:
    decision=registry.consider_promotion('verified',ArtifactRef.model_validate(packet['candidate']),ArtifactRef.model_validate(packet['evaluation']),PromotionPolicy.model_validate(packet['policy']),suite_ref=ArtifactRef.model_validate(packet['suite']))
except ValueError as exc:
    if mode != 'tamper': raise
    after=registry._pointer_path('verified').read_bytes()
    assert before == after
    print(json.dumps({'tamper_refused':True,'error_type':type(exc).__name__,'error':str(exc),'pointer_before_sha256':hashlib.sha256(before).hexdigest(),'pointer_after_sha256':hashlib.sha256(after).hexdigest(),'store_origin':sys.modules[FileSystemCAS.__module__].__file__}),flush=True)
else:
    assert mode != 'tamper', 'same exact ref with changed bytes must refuse'
    assert decision.promoted and decision.reason == 'promoted'
    after=registry._pointer_path('verified').read_bytes()
    assert before != after
    print(json.dumps({'decision':decision.model_dump(mode='json'),'pointer_before_sha256':hashlib.sha256(before).hexdigest(),'pointer_after_sha256':hashlib.sha256(after).hexdigest(),'store_origin':sys.modules[FileSystemCAS.__module__].__file__}),flush=True)
"""


def _prepared_successor(tmp_path):
    store, registry, suite_ref, policy, spec = _OWNER._environment(
        tmp_path, values=(1,), store_type=FileSystemCAS
    )
    result = SearchLoopRunner(store=store, registry=registry).run(
        spec, suite_ref=suite_ref, max_iterations=1
    )
    assert result.history[0].stage_b_result["simulation_results"]["score"] == 1.0
    candidate_ref, evaluation_ref = _OWNER._produce_pair(
        store, registry, suite_ref, policy, 2
    )
    packet = {
        "candidate": candidate_ref.model_dump(mode="json"),
        "evaluation": evaluation_ref.model_dump(mode="json"),
        "suite": suite_ref.model_dump(mode="json"),
        "policy": policy.model_dump(mode="json"),
    }
    packet_path = tmp_path / "prepared-successor.json"
    packet_path.write_text(json.dumps(packet, indent=2) + "\n")
    return store, registry, evaluation_ref, packet_path


def test_actual_owner_lock_blocks_child_publication_then_current_basis_commits(
    tmp_path,
):
    _, registry, _, packet_path = _prepared_successor(tmp_path)
    before = registry._pointer_path("verified").read_bytes()
    mode = (
        "remove-lock"
        if os.environ.get("E02_REMOVE_CHAMPION_LOCK") == "1"
        else "positive"
    )
    child = None
    try:
        with registry._promotion_lock("verified"):
            child = subprocess.Popen(
                [sys.executable, "-c", _CHILD, str(tmp_path), str(packet_path), mode],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=dict(os.environ),
            )
            ready = child.stdout.readline()
            print(ready, end="")
            assert json.loads(ready)["phase"] == "ready_before_actual_consider"
            try:
                completed, errors = child.communicate(timeout=0.5)
            except subprocess.TimeoutExpired:
                assert registry._pointer_path("verified").read_bytes() == before
            else:
                print(completed, errors)
                raise AssertionError(
                    "child publication escaped the actual held owner lock"
                )
    finally:
        if child is not None:
            completed, errors = child.communicate(timeout=10)
            print(completed, end="")
            print(errors, end="", file=sys.stderr)
    assert child is not None and child.returncode == 0
    pointer = registry.get("verified")
    assert pointer.metrics == {"score": 2.0}
    assert registry._pointer_path("verified").read_bytes() != before


def test_same_exact_evaluation_ref_changed_bytes_refuses_without_pointer_effect(
    tmp_path,
):
    store, registry, evaluation_ref, packet_path = _prepared_successor(tmp_path)
    before = registry._pointer_path("verified").read_bytes()
    data_path, _ = store._paths(evaluation_ref.artifact_id)
    original = data_path.read_bytes()
    assert hashlib.sha256(original).hexdigest() == evaluation_ref.artifact_id.hex
    changed = original + b"\n"
    data_path.write_bytes(changed)
    assert hashlib.sha256(changed).hexdigest() != evaluation_ref.artifact_id.hex
    child = subprocess.run(
        [sys.executable, "-c", _CHILD, str(tmp_path), str(packet_path), "tamper"],
        capture_output=True,
        text=True,
        env=dict(os.environ),
    )
    print(child.stdout, end="")
    print(child.stderr, end="", file=sys.stderr)
    assert child.returncode == 0, child.stdout + child.stderr
    assert '"tamper_refused": true' in child.stdout
    assert registry._pointer_path("verified").read_bytes() == before
    assert registry.get("verified").metrics == {"score": 1.0}
    print(
        json.dumps(
            {
                "same_exact_ref": evaluation_ref.model_dump(mode="json"),
                "original_data_sha256": hashlib.sha256(original).hexdigest(),
                "altered_data_sha256": hashlib.sha256(changed).hexdigest(),
                "pointed_incumbent_unchanged": True,
            },
            sort_keys=True,
        )
    )
