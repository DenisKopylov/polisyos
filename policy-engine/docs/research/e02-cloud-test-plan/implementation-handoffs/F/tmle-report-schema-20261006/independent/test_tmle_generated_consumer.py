"""Independent native/wire consumers for the existing TMLE enum companion.

Scratch-only; HTE fixtures establish serialization, not a native HTE producer.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import jsonschema
import numpy as np
import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.artifacts import get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.foundry.methods.catalog.causal.treatment_effects import TMLEEstimator
from polisyos.ir.analytics.causal import (
    CausalEffectReport, CausalMethod, EstimationStatus,
    load_causal_effect_report, persist_causal_effect_report,
)
from polisyos.ir.analytics.hte import HTEResult, load_hte_result, persist_hte_result
from tools.quality.diagnostics import gen_schema as generator

ROOT = Path('/workspace/e02-F-tmle-20261006')
ENGINE = ROOT / 'policy-engine'
SNAPSHOTS = ENGINE / 'schemas/snapshots/ir'
KEYS = ('causal_effect_report', 'hte_result')


def git(*args: str) -> bytes:
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


@pytest.fixture(scope='session', autouse=True)
def exact_source():
    pin = os.environ['REVIEW_SOURCE_SHA']
    paths = json.loads(Path(os.environ['REVIEW_SOURCE_PATHS']).read_text())
    assert git('rev-parse', 'HEAD').decode().strip() == pin
    expected = {}
    for name in paths:
        actual = (ROOT / name).read_bytes()
        assert actual == git('show', f'{pin}:{name}'), name
        expected[name] = hashlib.sha256(actual).hexdigest()
    yield
    assert git('rev-parse', 'HEAD').decode().strip() == pin
    assert expected == {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in paths}
    print('SOURCE_GUARD', json.dumps(dict(sha=pin, tree=git('rev-parse', 'HEAD^{tree}').decode().strip(), files=expected), sort_keys=True))


@pytest.fixture(scope='session')
def report():
    rng = np.random.default_rng(613)
    n = 360
    w = rng.choice([-1.0, 1.0], size=n)
    t = rng.binomial(1, 0.5, size=n).astype(float)
    y = rng.binomial(1, .25 + .1*w + .3*t).astype(float)
    result = TMLEEstimator.pure_step(
        {'X': w[:, None], 'treatment': t, 'outcome': y},
        {'propensity_backend': 'logistic', 'outcome_backend': 'linear',
         'calibration_mode': 'none', 'outcome_scaling': 'raw',
         'crossfit_folds': 3, 'n_repeats': 1, 'random_seed': 19,
         'ci_mode': 'wald', 'inference_profile': 'regular_iid',
         'coverage_guard': 'off'},
    )
    native = result['report']
    assert isinstance(native, CausalEffectReport)
    assert native.method is CausalMethod.TMLE
    assert native.status is EstimationStatus.SUCCESS
    assert native.confidence_interval is not None
    assert native.to_uncertainty_envelope().gate_eligible is False
    assert native.point_estimate == result['result']['ate']
    print('NATIVE_TMLE', json.dumps(dict(method=native.method.value, status=native.status.value,
        point=native.point_estimate, ci=native.confidence_interval, sample_size=native.sample_size,
        interval_method=result['result']['interval_method'], gate_eligible=False), sort_keys=True))
    return native


def hte_fixture(method=CausalMethod.TMLE):
    # Synthetic supported wire fixture, not an estimate from a native HTE job.
    return HTEResult.from_estimates(method=method, ate=.3, ate_ci_lower=.2,
        ate_ci_upper=.4, cate_values=[.2, .4], cate_std_values=[.01, .02],
        cate_ci_lower_values=[.1, .3], cate_ci_upper_values=[.3, .5],
        n_treated=1, n_control=1)


def schema(key):
    return json.loads((SNAPSHOTS / f'{key}.schema.json').read_text())


def typed_roundtrip(key, value, directory):
    writer = FileSystemCAS(directory)
    persist, load = ((persist_causal_effect_report, load_causal_effect_report)
                     if key == KEYS[0] else (persist_hte_result, load_hte_result))
    ref = persist(writer, value)
    payload = get_json_artifact(FileSystemCAS(directory), ref.artifact_id)
    jsonschema.Draft202012Validator(schema(key)).validate(payload)
    fresh = load(FileSystemCAS(directory), ref)
    assert fresh.model_dump(mode='json') == value.model_dump(mode='json')
    # A fresh process loads through the actual exported typed CAS reader.
    code = '''import json,sys
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal import load_causal_effect_report
from polisyos.ir.analytics.hte import load_hte_result
from polisyos.ir.registry.refs import CausalEffectReportRef, HTEResultRef
key,directory,serialized=sys.argv[1:]
cls,load=(CausalEffectReportRef,load_causal_effect_report) if key=="causal_effect_report" else (HTEResultRef,load_hte_result)
value=load(FileSystemCAS(directory),cls.model_validate_json(serialized))
print(value.model_dump_json())
'''
    proc = subprocess.run([sys.executable, '-c', code, key, str(directory), ref.model_dump_json()],
        text=True, capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr
    assert not proc.stderr
    assert json.loads(proc.stdout) == value.model_dump(mode='json')
    print('TYPED_FRESH_READER', json.dumps(dict(key=key, artifact_id=str(ref.artifact_id),
        payload_bytes=len(json.dumps(payload)), reader_exit=proc.returncode,
        schema_version=fresh.schema_version, method=fresh.method.value), sort_keys=True))
    return payload


def test_native_tmle_report_actual_cas_and_exported_schema(report, tmp_path):
    typed_roundtrip(KEYS[0], report, tmp_path / 'native')


def test_hte_tmle_supported_wire_actual_cas_and_exported_schema(tmp_path):
    typed_roundtrip(KEYS[1], hte_fixture(), tmp_path / 'wire')


@pytest.mark.parametrize('key', KEYS)
@pytest.mark.parametrize('explicit_version', (False, True))
def test_old_non_tmle_reports_remain_readable(key, explicit_version, report, tmp_path):
    value = (report.model_copy(update={'method': CausalMethod.DIFFERENCE_IN_DIFFERENCES})
             if key == KEYS[0] else hte_fixture(CausalMethod.CAUSAL_FOREST))
    payload = value.model_dump(mode='json')
    if not explicit_version:
        payload.pop('schema_version')
    writer = FileSystemCAS(tmp_path)
    raw_ref = put_json_artifact(writer, payload, kind=f'ir.{key}', schema_name=f'ir.{key}',
        schema_version='1.0', canon_spec=CanonSpec(forbid_floats=False))
    from polisyos.ir.registry.refs import CausalEffectReportRef, HTEResultRef
    cls, load = ((CausalEffectReportRef, load_causal_effect_report)
                 if key == KEYS[0] else (HTEResultRef, load_hte_result))
    ref = cls.model_validate(raw_ref)
    before = get_json_artifact(FileSystemCAS(tmp_path), ref.artifact_id)
    restored = load(FileSystemCAS(tmp_path), ref)
    assert restored.method is value.method
    assert restored.schema_version == '1.0'
    assert get_json_artifact(FileSystemCAS(tmp_path), ref.artifact_id) == before == payload
    jsonschema.Draft202012Validator(schema(key)).validate(payload)


@pytest.mark.parametrize('key', KEYS)
def test_unknown_enum_typed_and_snapshot_refusal(key, report):
    value = report if key == KEYS[0] else hte_fixture()
    payload = {**value.model_dump(mode='json'), 'method': 'unregistered_tmle_variant'}
    cls = CausalEffectReport if key == KEYS[0] else HTEResult
    with pytest.raises(ValidationError, match='method'):
        cls.model_validate(payload)
    with pytest.raises(jsonschema.ValidationError, match='enum'):
        jsonschema.Draft202012Validator(schema(key)).validate(payload)


@pytest.mark.parametrize('key', KEYS)
def test_missing_tmle_exported_enum_rejects_actual_wire(key, report, tmp_path):
    value = report if key == KEYS[0] else hte_fixture()
    payload = typed_roundtrip(key, value, tmp_path / 'retained-typed-consumer')
    corrupt = schema(key)
    corrupt['$defs']['CausalMethod']['enum'].remove('tmle')
    # Provider enum/markers/version remain real; only export enum property removed.
    assert CausalMethod.TMLE.value == 'tmle'
    assert value.schema_version == '1.0'
    with pytest.raises(jsonschema.ValidationError, match='enum'):
        jsonschema.Draft202012Validator(corrupt).validate(payload)


@pytest.mark.parametrize('key', KEYS)
def test_canonical_snapshot_matches_fresh_model_generation(key):
    entry = generator.select_abi_entries([key])[0]
    payload = generator._load_or_generate_entry_payload(generator._resolve_entry(entry),
        cache_root=None, pydantic_version=generator._import_version('pydantic'))
    errors = []
    generator._assert_file_equals(SNAPSHOTS / entry.schema_file,
        generator._json_dump(payload['schema_payload'], fmt='pretty'), errors)
    assert errors == []
    manifest = json.loads((SNAPSHOTS / '_manifest.json').read_text())
    row = manifest['models'][key]
    assert row['sha256_full'] == payload['sha256_full']
    assert row['sha256_semantic'] == payload['sha256_semantic']
    assert row['schema_version'] == payload['schema_version'] == '1.0'


def test_manifest_preserves_97_unowned_entries_and_provenance():
    base = os.environ['REVIEW_BASE_SHA']
    original = json.loads(git('show', f'{base}:policy-engine/schemas/snapshots/ir/_manifest.json'))
    current = json.loads((SNAPSHOTS / '_manifest.json').read_text())
    assert len(current['models']) == len(original['models']) == 99
    assert {k:v for k,v in current.items() if k not in ('models','content_hash')} == {
        k:v for k,v in original.items() if k not in ('models','content_hash')}
    assert {k:v for k,v in current['models'].items() if k not in KEYS} == {
        k:v for k,v in original['models'].items() if k not in KEYS}
    assert current['content_hash'] == generator._schema_hash(current['models'])
    assert current['content_hash'] != original['content_hash']


@pytest.mark.parametrize('key', KEYS)
def test_real_checker_detects_missing_export_enum(key):
    target = SNAPSHOTS / f'{key}.schema.json'
    original = target.read_text()
    corrupt = json.loads(original)
    corrupt['$defs']['CausalMethod']['enum'].remove('tmle')
    changed = generator._json_dump(corrupt, fmt='pretty')
    read = Path.read_text
    errors = []
    with patch.object(Path, 'read_text', lambda p,*a,**kw: changed if p == target else read(p,*a,**kw)):
        generator._assert_file_equals(target, original, errors)
    assert errors == [f'snapshot out of date: {target}']
    print('ENUM_CORRUPTION_DETECTED', key, errors)


@pytest.mark.parametrize('key', KEYS)
def test_real_checker_detects_model_hash_corruption(key):
    target = SNAPSHOTS / '_manifest.json'
    expected = json.loads(target.read_text())
    corrupt = copy.deepcopy(expected)
    corrupt['models'][key]['sha256_full'] = '0'*64
    corrupt['content_hash'] = generator._schema_hash(corrupt['models'])
    read = Path.read_text
    errors = []
    with patch.object(Path, 'read_text', lambda p,*a,**kw: json.dumps(corrupt) if p == target else read(p,*a,**kw)):
        generator._assert_manifest_equals(target, expected, errors)
    assert errors == [f'snapshot out of date: {target}']
    print('MODEL_HASH_CORRUPTION_DETECTED', key, errors)
