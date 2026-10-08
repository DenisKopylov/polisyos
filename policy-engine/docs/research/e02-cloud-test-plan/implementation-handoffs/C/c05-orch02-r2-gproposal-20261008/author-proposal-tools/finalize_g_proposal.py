"""Finalize owned public-seam proposal without applying product files."""
import ast,difflib,hashlib,json,subprocess
from pathlib import Path
root=Path('/workspace/orch02-r2/c05/g-patch')
repo=Path('/workspace/orch02-c05-r2-gproposal')
d=json.loads((root/'reconciliation.json').read_text())
patch=[]
for row in d['paths']:
 folder=Path(row['folder']);s=(folder/'postimage').read_text();path=row['path']
 if path.endswith('batch/config.py'):
  s=s.replace('    from polisyos.fabric.connectors import resolve_connection_config\n    from polisyos.fabric.connectors.profiles import SourceProfileRegistry\n    from polisyos.fabric.connectors.profiles.resolver import resolve_execution_policy\n','    from polisyos.fabric import (\n        SourceProfileRegistry,\n        resolve_connection_config,\n        resolve_execution_policy,\n    )\n')
 if path.endswith('core_sources/loaders.py'):
  s=s.replace('from polisyos.ir.connectors import FetchRequest','from polisyos.ir import FetchRequest').replace('    from polisyos.ir.connectors import FetchResult','    from polisyos.ir import FetchResult').replace('    from polisyos.fabric.connectors.profiles.models import SourceExecutionPolicy','    from polisyos.fabric import SourceExecutionPolicy')
 if path.endswith('fabric/retrieval/service.py'):
  s=s.replace('    from polisyos.core.artifacts import ArtifactStore, ArtifactStoreConfig','    from polisyos.core import ArtifactStore, ArtifactStoreConfig').replace('    from polisyos.data_forge.domains.catalog import (','    from polisyos.data_forge.read_api.catalog import (')
 after=s.encode();before=(folder/'G').read_bytes()
 if path.endswith('.py'):ast.parse(s);compile(s,path,'exec')
 (folder/'postimage').write_bytes(after)
 old=row['preimage_blob'] or '0'*40
 new=subprocess.check_output(['git','hash-object','--stdin'],input=after,cwd=repo).decode().strip()
 header=f'diff --git a/{path} b/{path}\n'+('new file mode 100644\n' if not before else '')+f'index {old}..{new}'+(' 100644' if before else '')+'\n'
 delta=''.join(difflib.unified_diff(before.decode().splitlines(keepends=True),s.splitlines(keepends=True),fromfile='a/'+path if before else '/dev/null',tofile='b/'+path))
 patch.append(header+delta)
 row.update(postimage_blob=new,postimage_sha256=hashlib.sha256(after).hexdigest(),postimage_bytes=len(after))
raw=''.join(patch).encode();(root/'owned-g-proposal.patch').write_bytes(raw)
d.update(patch_sha256=hashlib.sha256(raw).hexdigest(),patch_bytes=len(raw),r2_source='5ccbfa15c5671623a4c1ff7a3145460c5ca5a857',public_seam_requirement='foreign-public-companions.patch: canonical aliases must be selected before the proposed root imports can resolve',G_native_claim=False,formal_closure_ids=[])
commands=[]
for name,args in [('owned',['owned-g-proposal.patch']),('combined',['owned-g-proposal.patch','foreign-public-companions.patch'])]:
 argv=['git','apply','--check']+[str(root/a) for a in args]
 r=subprocess.run(argv,cwd=repo,capture_output=True)
 for stream in ['stdout','stderr']:(root/f'{name}-apply-check.{stream}.txt').write_bytes(getattr(r,stream))
 commands.append(dict(name=name,argv=argv,cwd=str(repo),exit_code=r.returncode))
 assert r.returncode==0,r.stderr.decode()
d['apply_checks']=commands
(root/'reconciliation.json').write_text(json.dumps(d,indent=2)+'\n')
print(json.dumps({k:d[k] for k in ['state','patch_sha256','patch_bytes','r2_source']},indent=2))
