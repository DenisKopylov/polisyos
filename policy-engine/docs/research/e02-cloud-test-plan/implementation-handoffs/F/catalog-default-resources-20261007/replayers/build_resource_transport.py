"""Build complete lossless resource evidence carriers, outside the product checkout."""
from pathlib import Path
import argparse, gzip, hashlib, json, shutil
PARSER=argparse.ArgumentParser()
PARSER.add_argument('--api-selection',type=Path)
PARSER.add_argument('--output',type=Path,required=True)
args=PARSER.parse_args()
base=Path('/tmp/e02-F-continuation-20261007/graph/packaged-default-diagnosis')
fit=Path('/tmp/e02-F-continuation-20261007/fit-tmle/dataforge-resource-review')
foundry=Path('/tmp/e02-F-continuation-20261007/foundry/installed-continuation-final')
relative=Path('policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/catalog-default-resources-20261007')
selected={}
def add(path,category,expected=None):
 path=Path(path).resolve()
 body=path.read_bytes()
 if expected:
  assert len(body)==expected['bytes'],path
  assert hashlib.sha256(body).hexdigest()==expected['sha256'],path
 if path not in selected:selected[path]=(category,body)
for path in sorted(base.iterdir()):
 if path.is_file():add(path,'author')
add('/tmp/e02-F-continuation-20261007/graph/run_check.py','replayers')
add(__file__,'replayers')
add('/tmp/e02-F-continuation-20261007/graph/verify_resource_transport.py','replayers')
add('/tmp/e02-F-continuation-20261007/graph/write_resource_receipt.py','replayers')
add('/tmp/e02-F-continuation-20261007/graph/validate_resource_receipt.py','replayers')
selection=json.loads((fit/'transfer-selection.json').read_text())
add(fit/'transfer-selection.json','fit-design')
for row in selection['files']:add(row['path'],'fit-design',row)
for row in selection['external_existing_owner_files']:add(row['path'],'author',row)
for name in ['graph-diagnostic.stdout.txt','graph-diagnostic.stderr.txt','graph-diagnostic-v2.stdout.txt','graph-diagnostic-v2.stderr.txt','auxiliary-diagnostic-classification.json','installed-config.json']:
 add(foundry/name,'foundry-b5')
add(foundry/'wheel-consumer'/'diagnose_graph.py','foundry-b5')
if args.api_selection:
 add(args.api_selection,'api-review')
 api=json.loads(args.api_selection.read_text())
 rows=api.get('files',api.get('items',api.get('selected_files')))
 assert rows is not None,'unknown explicit API selection grammar'
 for row in rows:
  path=row.get('path',row.get('source_path'))
  assert path
  add(path,'api-review',row)
args.output.mkdir(exist_ok=True,parents=True)
files=[]
locators={}
for path,(category,body) in sorted(selected.items(),key=lambda x:str(x[0])):
 name=path.name
 # Preserve artifact whitespace as data; no log normalization or lossy summary.
 compressed=any(marker in name for marker in ['.stdout.','.stderr.']) or name.endswith(('.patch','.xml')) or len(body)>100000
 output=Path(category)/name
 if compressed:output=output.with_name(output.name+'.gz');stored=gzip.compress(body,mtime=0)
 else:stored=body
 destination=args.output/output;destination.parent.mkdir(parents=True,exist_ok=True)
 assert not destination.exists() or destination.read_bytes()==stored,destination
 destination.write_bytes(stored)
 row={'path':str(relative/output),'bytes':len(stored),'sha256':hashlib.sha256(stored).hexdigest(),'original_execution_path':str(path),'role':category,'encoding':'gzip' if compressed else 'identity'}
 if compressed:row.update(decoded_bytes=len(body),decoded_sha256=hashlib.sha256(body).hexdigest(),decompressed_bytes=len(body),decompressed_sha256=hashlib.sha256(body).hexdigest())
 files.append(row);locators[str(path)]=row
manifest={'schema':'policyos.e02.full_output_manifest.v1','files':files,'raw_artifact_data':'Complete unchanged source-observed and native outputs; gzip storage is lossless transport only. Scratch originals retained. No production input files copied.'}
(args.output/'outputs.json').write_text(json.dumps(manifest,indent=2)+'\n')
(args.output/'execution-to-git-locators.json').write_text(json.dumps(locators,indent=2)+'\n')
print(json.dumps({'files':len(files),'stored_bytes':sum(r['bytes'] for r in files),'decoded_gzip_files':sum(r['encoding']=='gzip' for r in files),'decoded_gzip_bytes':sum(r.get('decoded_bytes',0) for r in files),'output':str(args.output)},indent=2))
