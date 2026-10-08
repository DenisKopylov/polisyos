import hashlib,json,pathlib,platform,subprocess,sys
import networkx,numpy,pydantic
binary=pathlib.Path(sys.executable).resolve()
worker='/workspace/e02-F-dowhy-20261006/policy-engine/workers/dowhy-014/.venv/bin/python'
code="import json,platform,sys,dowhy; print(json.dumps({'python':platform.python_version(),'executable':sys.executable,'dowhy':dowhy.__version__,'dowhy_origin':dowhy.__file__}))"
worker_result=subprocess.run([worker,'-c',code],capture_output=True)
assert worker_result.returncode==0,worker_result.stderr.decode()
print(json.dumps({'actual_application':{'python':platform.python_version(),'executable':sys.executable,'resolved_executable':str(binary),'executable_bytes':binary.stat().st_size,'executable_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'packages':[{'name':m.__name__,'version':m.__version__,'origin':m.__file__} for m in [networkx,numpy,pydantic]]},'actual_selected_worker_environment':json.loads(worker_result.stdout),'scope':'Read-only current runtime probe, not a retroactive exact patch-version measurement of prior execution records lacking version identity.'},indent=2))
