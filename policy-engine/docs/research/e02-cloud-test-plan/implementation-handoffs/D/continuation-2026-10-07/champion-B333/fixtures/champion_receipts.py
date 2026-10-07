"""Readonly fresh-process actual pointer/basis/CAS evidence after passed consumers."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

_READER = r"""
import hashlib,json,os,sys
from pathlib import Path
from polisyos.core.artifacts.manifest import artifact_ref_identity_key
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.autotune.models import BenchmarkEvaluation,PromotionPolicy,benchmark_comparison_basis,load_model_artifact
from polisyos.scientist.methods.autotune.registry import ChampionRegistry
root=Path(sys.argv[1]); store=FileSystemCAS(root/'cas')
registry=ChampionRegistry(root/'champions',store=store)
pointer=registry.get('verified'); assert pointer is not None
evaluation=load_model_artifact(store,pointer.evaluation_ref,BenchmarkEvaluation)
assert evaluation.candidate_ref == pointer.candidate_ref
assert evaluation.holdout_metrics == pointer.metrics
basis=evaluation.comparison_basis; assert basis is not None
policy=PromotionPolicy.model_validate(pointer.metadata['promoted_by_policy'])
assert basis == benchmark_comparison_basis(store,basis.suite_ref,policy,basis.evaluator_profile)
records=[]; seen=set()
def add(role,ref):
    if ref is None: return
    key=artifact_ref_identity_key(ref)
    if key in seen: return
    seen.add(key)
    snapshot=store.get_verified_snapshot(ref)
    assert hashlib.sha256(snapshot.data).hexdigest() == ref.artifact_id.hex
    assert snapshot.actual_sha256_hex == ref.artifact_id.hex
    records.append({'role':role,'ref':ref.model_dump(mode='json'),'data_sha256':hashlib.sha256(snapshot.data).hexdigest(),'manifest_sha256':hashlib.sha256(snapshot.manifest_bytes).hexdigest(),'data_utf8':snapshot.data.decode(),'manifest_utf8':snapshot.manifest_bytes.decode()})
for role,ref in [('candidate',pointer.candidate_ref),('evaluation',pointer.evaluation_ref),('suite',basis.suite_ref),('dataset',basis.dataset_ref),('split',basis.split_manifest_ref),('incumbent_evaluation',evaluation.incumbent_evaluation_ref),('predecessor_candidate',evaluation.comparison_predecessor_candidate_ref),('predecessor_evaluation',evaluation.comparison_predecessor_evaluation_ref)]: add(role,ref)
if basis.dataset_ref is not None:
    rows=[json.loads(line) for line in store.get_verified_snapshot(basis.dataset_ref).data.decode().splitlines()]
    split=json.loads(store.get_verified_snapshot(basis.split_manifest_ref).data)
    candidate=json.loads(store.get_verified_snapshot(pointer.candidate_ref).data)
    independent_score=candidate['value']*sum(row['weight'] for row in rows if str(row['id']) in split['holdout_ids'])
    assert pointer.metrics == {'score':float(independent_score)}
else: independent_score=None
packet={'selector':sys.argv[2],'pid':os.getpid(),'store_origin':sys.modules[FileSystemCAS.__module__].__file__,'registry_origin':sys.modules[ChampionRegistry.__module__].__file__,'pointer':pointer.model_dump(mode='json'),'comparison_basis':basis.model_dump(mode='json'),'canonical_policy':policy.model_dump(mode='json'),'independent_controlled_arithmetic_score':independent_score,'pointer_sha256':hashlib.sha256(registry._pointer_path('verified').read_bytes()).hexdigest(),'actual_verified_reads':records}
print(json.dumps(packet,sort_keys=True),flush=True)
"""


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.passed:
        return
    root = item.funcargs.get("tmp_path")
    if root is None or not (Path(root) / "champions/verified/champion.json").is_file():
        return
    reader = subprocess.run(
        [sys.executable, "-c", _READER, str(root), item.nodeid],
        capture_output=True,
        text=True,
        env=dict(os.environ),
    )
    evidence = Path(os.environ["E02_CHAMPION_EVIDENCE"])
    name = item.name.replace("/", "_")
    (evidence / (name + ".fresh.stdout.txt")).write_text(reader.stdout)
    (evidence / (name + ".fresh.stderr.txt")).write_text(reader.stderr)
    (evidence / (name + ".fresh.exit.json")).write_text(
        json.dumps({"returncode": reader.returncode, "selector": item.nodeid}) + "\n"
    )
    assert reader.returncode == 0, reader.stdout + reader.stderr
    packet = json.loads(reader.stdout)
    (evidence / (name + ".fresh.json")).write_text(json.dumps(packet, indent=2) + "\n")
    report.sections.append(("fresh canonical B CAS/champion proof", reader.stdout))
