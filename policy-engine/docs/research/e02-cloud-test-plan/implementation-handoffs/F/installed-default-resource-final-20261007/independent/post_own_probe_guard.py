"""Re-read complete active site/archive bytes after own two cheap consumers."""
import hashlib,json,pathlib
OUT=pathlib.Path(__file__).resolve().parent;P=pathlib.Path('/tmp/e02-F-continuation-20261007/foundry/installed-default-resource-forward');b=json.loads((P/'archive-installed-source-bindings.json').read_text());config=json.loads((P/'installed-config.json').read_text());checks=0
for kind,path in config['sites'].items():
 site=pathlib.Path(path)
 for row in b['source_bindings']:
  raw=(site/row['destination']).read_bytes();assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'];checks+=1
 actual={p.relative_to(site).as_posix() for ns in ['polisyos','tools'] for p in (site/ns).rglob('*.py')};assert actual=={r['destination'] for r in b['source_bindings'] if r['destination'].endswith('.py')}
for key,row in b['archives'].items():raw=pathlib.Path(row['path']).read_bytes();assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
result={'source_sha':config['source_sha'],'source_tree':config['source_tree'],'outcome':'PASS','complete_active_site_checks':checks,'active_archives':len(b['archives']),'extra_missing_actual_python':[],'scope':'After own1native6ownerconsumer/profile; completeactiveproduct+11resourcebytes andthreearchives unchanged. Historicalretiredoldarchives notreread.'};(OUT/'post-own-probe-guard.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
