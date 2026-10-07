import hashlib, json, os, pathlib, platform, subprocess, sys, time
repo=pathlib.Path(__file__).resolve().parents[3]
product=repo/'policy-engine'
name=sys.argv[1]
selectors=sys.argv[2:]
root=pathlib.Path(__file__).resolve().parent/name
root.mkdir(exist_ok=True)
python=str(product/'.venv/bin/python')
env=dict(os.environ, PYTHONPATH=str(product/'src')+':'+str(product), OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1', JAX_PLATFORMS='cpu')
plugin=root/'e02_origin.py'
plugin.write_text("import importlib.metadata,json,pathlib,sys\ndef pytest_sessionfinish(session,exitstatus):\n payload={'python':sys.version,'executable':sys.executable,'module_origins':{k:getattr(v,'__file__',None) for k,v in sys.modules.items() if k in ['polisyos.runtime.quality.generation_cycle','polisyos.runtime.quality.joint_simulation_horizon','polisyos.runtime.quality.design_axes.coupling_composition','polisyos.calibration.forecast_bridge','polisyos.core.artifacts.store']},'versions':{k:importlib.metadata.version(k) for k in ['pytest','pydantic','numpy','scipy']}}\n pathlib.Path(__file__).with_name('origins.json').write_text(json.dumps(payload,indent=2)+chr(10))\n")
probe=product/'_build/e02-A-full-queue/remove-width-property-probe/e02_remove_width_property_probe.py'
env['PYTHONPATH']=str(root)+':'+str(probe.parent)+':'+env['PYTHONPATH']
cmd=[python,'-m','pytest','-p','e02_origin','-p','e02_remove_width_property_probe','-s','-o','addopts=','--import-mode=importlib','--strict-markers','-q','--junitxml='+str(root/'junit.xml'),'--basetemp='+str(root/'pytest-basetemp'),*selectors]
head=subprocess.check_output(['git','rev-parse','HEAD','HEAD^{tree}'],cwd=repo,text=True).splitlines()
start=time.monotonic()
with (root/'stdout.txt').open('wb') as out,(root/'stderr.txt').open('wb') as err:
 result=subprocess.run(cmd,cwd=product,env=env,stdout=out,stderr=err,timeout=900)
receipt={'argv':cmd,'cwd':str(product),'candidate_sha':head[0],'candidate_tree':head[1],'exit_code':result.returncode,'wall_s':time.monotonic()-start,'environment':{k:env[k] for k in ['PYTHONPATH','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','JAX_PLATFORMS']},'probe_environment':{k:env[k] for k in ['POLISYOS_TEST_S10_NULLABLE_RATE_REMOVAL','POLISYOS_SIM03_PHYSICAL_IDENTITY_REMOVAL_PROBE'] if k in env},'mutation_plugin':{'path':str(probe),'sha256':hashlib.sha256(probe.read_bytes()).hexdigest()},'launcher':{'path':str(pathlib.Path(__file__).resolve()),'sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()},'outputs':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in root.iterdir() if p.is_file()}}
(root/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
