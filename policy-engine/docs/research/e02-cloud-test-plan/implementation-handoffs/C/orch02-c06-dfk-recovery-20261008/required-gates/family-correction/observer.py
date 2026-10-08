import argparse, dataclasses, datetime, hashlib, json, pathlib, resource, subprocess, sys, time
p=argparse.ArgumentParser();p.add_argument('--role',choices=['dfk','can'],required=True);a=p.parse_args()
repo=pathlib.Path('/workspace/orch02-c06-'+a.role);engine=repo/'policy-engine';frozen={'dfk':'cbbfffd367fe283813a8177575d26c0ede8d20c4','can':'4901e26841e2be0ae6ef393754abed5cafb1e2d4'}[a.role]
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==frozen
sys.path[:0]=[str(engine),str(engine/'src')]
from tools.devx.architecture import guardrails as g
assert g.REPO_ROOT==engine
retained=pathlib.Path('/workspace/orch02-recovery/c06-required-'+a.role+'-architecture/generated-freshness');isolated=retained/'source'
out=pathlib.Path('/workspace/orch02-recovery/c06-required-'+a.role+'-family-correction');out.mkdir()
names=['runtime-dashboard-api-types','trust-claim-posture-register'] if a.role=='dfk' else ['trust-claim-posture-register']
families=g._parse_generated_artifacts(g.DEFAULT_GENERATED_MANIFEST);selected=tuple(f for f in families if f.family_id in names);assert len(selected)==len(names)
cursor=g._GeneratedArtifactMeasurementCursor(selected,[],[])
expected=g._expected_output_snapshot(list(selected),expected_root=engine);owners={}
for family in families:
 for output in family.outputs:
  relative=g._relative_generated_output(output)
  if relative is not None:owners.setdefault(relative,[]).append(family.family_id)
environment=g._isolated_probe_environment(isolated,uv_cache_dir=pathlib.Path('/workspace/.polisyos-environment/cache/uv'),offline=True)
original_run=g.subprocess.run;events=[];active=None
# Observe complete generator subprocess results; the original gate and command are unchanged.
def observed_run(argv,*args,**kwargs):
 start=time.perf_counter();started=datetime.datetime.now(datetime.timezone.utc).isoformat();result=original_run(argv,*args,**kwargs)
 if active is not None and list(argv)==active['argv']:
  prefix=out/active['family'];prefix.mkdir()
  outputs={}
  for name,value in [('stdout.txt',result.stdout or ''),('stderr.txt',result.stderr or '')]:
   data=value.encode();(prefix/name).write_bytes(data);outputs[name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
  e={'argv':list(argv),'cwd':str(kwargs.get('cwd')),'started_utc':started,'wall_seconds':time.perf_counter()-start,'returncode':result.returncode,'complete_outputs':outputs,'capture_semantics':'Original guardrails subprocess.run capture_output=True,text=True; complete decoded text re-encoded UTF-8.','selected_environment':{k:environment.get(k) for k in ['PATH','PYTHONPATH','PYTHONNOUSERSITE','PYTHONDONTWRITEBYTECODE','UV_PROJECT_ENVIRONMENT','UV_CACHE_DIR','UV_NO_SYNC','UV_OFFLINE']}}
  (prefix/'command.json').write_text(json.dumps(e,indent=2)+'\n');events.append(e)
 return result
g.subprocess.run=observed_run
for i,family in enumerate(selected):
 scratch=out/'outputs'/family.family_id
 active={'family':family.family_id,'argv':[part.replace('{output_root}',str(scratch)) for part in family.output_probe_command]}
 g._measure_required_generated_artifact_family(family,family_index=i,cursor=cursor,family_scratch_root=scratch,isolated_repo_root=isolated,environment=environment,expected_root=engine,expected_outputs=expected,declared_owners=owners)
g.subprocess.run=original_run
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==frozen
result={'source_sha':frozen,'guardrails_path':str(pathlib.Path(g.__file__)),'guardrails_sha256':hashlib.sha256(pathlib.Path(g.__file__).read_bytes()).hexdigest(),'retained_source':str(isolated),'retained_environment':str(retained/'environment'),'selected_families':names,'original_full_gate':'/workspace/orch02-recovery/c06-required-'+a.role+'-architecture','reason':'Writer concurrently packaged handoff files during original worktree isolation snapshots; repeat only affected family measurements with own lane writes suspended.','scope':'Narrow correction, not full architecture PASS or inherited-baseline verdict.','violations':[dataclasses.asdict(x) for x in cursor.violations],'unrun':[dataclasses.asdict(x) for x in cursor.unrun_checks],'commands':events}
(out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(bool(cursor.violations or cursor.unrun_checks))
