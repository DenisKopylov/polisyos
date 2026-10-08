# Bounded DDM custody discriminator

Product source: `f00dd7661a8d3329fb1fa1b049decb0d1d2f277b`, tree
`d9a4e73a0e85fa11f865bf643c1b63fbe66c2767`. Production and tests are unchanged.

The maintained selectors are `test_full_acceptance.py::test_registry_public_round_trip_rebinds_with_exact_context`,
`::test_registry_rebind_rejects_tampered_validity_projection`, and
`::test_registry_distinguishes_unavailable_from_observed_empty_triggers` under `policy-engine/tests/unit/ddm/`.
Invoke Python 3.14 with the selected checkout's `src` and `tests` on PYTHONPATH,
`python -m pytest -o addopts='' -p no:cacheprovider --import-mode=importlib -q -s`,
all three exact node IDs, a new isolated `--basetemp`, and `--junitxml`.
Six cases passed. The cache-provider warning is tooling output, not a product failure.

For the matched removal, in a separate interpreter import
`polisyos.ddm.calibration.audit`, set only
`_IMMUTABLE_VALIDITY_PROJECTION_FIELDS = ()`, then call `pytest.main` on
`::test_registry_rebind_rejects_tampered_validity_projection` with the same flags
and a different scratch directory. DTO fields, verifier labels and files remain intact.
All four cases fail because the tampered projection can now pass `R4_promotion_allowed`.
The executed check outcome is FAIL; the independent sensitivity interpretation is PASS.

Fresh-process recipe follows. It persists synthetic report/audit/registry bytes from
the maintained fixture and reruns the real checker and gate in each new interpreter.
It establishes round-trip/currentness mechanics only. It does not establish factual
calibration, measured holdout, an institutional signoff or a production observation feed.
Each child has an explicit 60-second timeout; measured total child wall time is 0.311 seconds
and maximum child RSS is 36,700,160 bytes on this macOS environment.

```python
from __future__ import annotations
import importlib.util,json,pathlib,subprocess,sys,time,resource
root=pathlib.Path.cwd();out=root/'_build/e02-L01-20261008/checks/ddm-fresh'
spec=importlib.util.spec_from_file_location('l01_existing_ddm_test',root/'tests/unit/ddm/test_full_acceptance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
report,audit,record=m._registry_context(observed_triggers=[])
projection=record.calibration_validity
assert projection is not None
packet={'report':report.model_dump(mode='json'),'audit':audit.model_dump(mode='json'),'record':record.model_dump(mode='json'),'now':projection.effective_at.isoformat()}
(out/'synthetic-persisted-context.json').write_text(json.dumps(packet)+'\n')
child="""
import json,pathlib,sys
from datetime import datetime
from polisyos.ddm.calibration import CalibrationReport
from polisyos.ddm.integration import CalibrationAudit,ModelRegistryReadinessRecord,evaluate_registry_gate
from polisyos.ddm.integration.model_registry import rebind_calibration_validity
p=json.loads(pathlib.Path(sys.argv[1]).read_text());mode=sys.argv[2]
if mode=='tampered':p['record']['calibration_validity']['report_digest']='0'*64
report=CalibrationReport.model_validate(p['report']);audit=CalibrationAudit.model_validate(p['audit']);record=ModelRegistryReadinessRecord.model_validate(p['record'])
prior=evaluate_registry_gate(record);assert not prior.promotion_allowed
rebound=rebind_calibration_validity(record,report=report,calibration_audit=audit,now=datetime.fromisoformat(p['now']),observed_invalidation_triggers=None if mode=='missing' else [])
gate=evaluate_registry_gate(rebound)
expected={'valid':(True,'R4_promotion_allowed'),'tampered':(False,'calibration_report_binding_not_established'),'missing':(False,'calibration_validity_not_established')}[mode]
assert (gate.promotion_allowed,gate.reason)==expected,(mode,gate)
print(json.dumps({'mode':mode,'fresh_process':True,'pre_rebind_allowed':prior.promotion_allowed,'allowed':gate.promotion_allowed,'reason':gate.reason},sort_keys=True))
"""
started=time.monotonic()
for mode in ('valid','tampered','missing'):
 r=subprocess.run([sys.executable,'-c',child,str(out/'synthetic-persisted-context.json'),mode],capture_output=True,text=True,timeout=60)
 (out/(mode+'.stdout')).write_text(r.stdout);(out/(mode+'.stderr')).write_text(r.stderr)
 print(r.stdout,end='');assert r.returncode==0,(mode,r.returncode,r.stderr)
print(json.dumps({'fixture':'synthetic existing _registry_context; no factual issuer/source law admitted','child_timeout_s':60,'wall_s':time.monotonic()-started,'max_child_rss_bytes_macos':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss}))
```
