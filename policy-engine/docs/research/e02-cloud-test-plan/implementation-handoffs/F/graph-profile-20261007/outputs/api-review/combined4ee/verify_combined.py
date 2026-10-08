import ast,hashlib,json,re,subprocess,tomllib,xml.etree.ElementTree as ET
from pathlib import Path
R=Path('/workspace/e02-F-closeout-20261006')
O=Path('/tmp/e02-F-graph-profile-20261007/api-review/combined4ee')
H='4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d';B='25cdea9064ddea2c3a812fd68670076bd4b088cb'
parts={'graph':'36b18cc142aff77a5825126b4f07bafec09a5180','benchmark':'e1c4bb28c9d5ff936ae1c047619c56cf12ba5347','docs':'6beacc8b42dacabff214901919203323f07d1fef'}
def git(*args):return subprocess.check_output(['git',*args],cwd=R)
def ref(p):
 p=Path(p);raw=p.read_bytes();return {'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def bind(sha,p):
 raw=git('show',sha+':'+p);return {'source_sha':sha,'path':p,'git_blob':git('rev-parse',sha+':'+p).decode().strip(),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
assert git('rev-parse',H+'^{tree}').decode().strip()=='551d4e760dc1168f6ad8182c9b176f00e94a2281'
allpaths=set(git('diff','--name-only',B,H).decode().splitlines());bindings=[];union=set()
for group,sha in parts.items():
 subprocess.run(['git','merge-base','--is-ancestor',sha,H],cwd=R,check=True)
 paths=git('diff','--name-only',B,sha).decode().splitlines()
 assert len(paths)=={'graph':6,'benchmark':1,'docs':3}[group]
 assert not union.intersection(paths);union.update(paths)
 for p in paths:
  assert git('show',H+':'+p)==git('show',sha+':'+p)==(R/p).read_bytes()
  bindings.append({'group':group,'component':bind(sha,p),'candidate':bind(H,p),'working_bytes_equal_candidate':True,'candidate_equals_component':True})
assert len(allpaths)==10 and union==allpaths
patch=git('diff','--binary',B,H);(O/'combined.full.patch').write_bytes(patch)
# Full bounded input closure for the author's scoped docs evidence.
doc=Path('/tmp/e02-F-graph-profile-20261007/foundry/layout-docs.json');dr=json.loads(doc.read_text())
assert dr['source_sha']==parts['docs'] and dr['outcome']=='PASS' and dr['exit_code']==0
docs_inputs=[]
for expected in dr['source_inputs']:
 p=Path(expected['path']);assert ref(p)==expected
 relative=p.relative_to('/workspace/e02-F-fry-20261006').as_posix()
 assert p.read_bytes()==git('show',H+':'+relative)==(R/relative).read_bytes()
 docs_inputs.append({'author_file':expected,'current':bind(H,relative),'candidate_equals_author_inputs':True})
for key in ['stdout','stderr','config','html']:
 assert ref(dr[key]['path'])==dr[key]
html=Path(dr['html']['path']).read_text();anchors=dr['complete_native_layout_anchors']
assert len(anchors)==5 and all('id="'+x+'"' in html for x in anchors)
layout=Path('/tmp/e02-F-graph-profile-20261007/foundry/layout-native.execution.json');lr=json.loads(layout.read_text())
assert lr['source_sha']==parts['docs'] and lr['exit_code']==0
for key in ['stdout','stderr']:assert ref(lr[key]['path'])==lr[key]
lt=ET.parse('/tmp/e02-F-graph-profile-20261007/foundry/layout-native.xml').getroot();suite=next(lt.iter('testsuite'))
assert {k:int(suite.attrib[k]) for k in ['tests','errors','failures','skipped']}=={'tests':6,'errors':0,'failures':0,'skipped':0}
contract=tomllib.loads(git('show',H+':policy-engine/architecture/public_surface/contract.toml').decode())
addresses=['polisyos.foundry.methods.layout','polisyos.foundry.methods.compiler.layout']
entrypoints=[name for row in contract['package'] for name in row.get('supported_entrypoints',[])]
assert all(p not in entrypoints for p in addresses)
assert contract['public_surface']['internal_rule']=='Any polisyos module path not listed in this manifest is internal by default.'
exports={'SlotFamily','SlotFamilyManifest','SlotLayout','build_slot_family_manifest','build_slot_layout'}
facades=[]
for p in ['policy-engine/src/polisyos/foundry/methods/layout.py','policy-engine/src/polisyos/foundry/methods/compiler/layout.py']:
 parsed=ast.parse(git('show',H+':'+p));imports=[n for n in parsed.body if isinstance(n,ast.ImportFrom)]
 assert len(imports)==1 and imports[0].module=='polisyos.ir.kernel.slots'
 assert {x.name for x in imports[0].names}==exports
 assert not any(isinstance(n,(ast.FunctionDef,ast.ClassDef)) for n in parsed.body)
 facades.append(bind(H,p))
trinity='policy-engine/src/polisyos/foundry/compile/trinity_compiler.py'
ttree=ast.parse(git('show',H+':'+trinity));assert any(isinstance(n,ast.ImportFrom) and n.module=='polisyos.ir.kernel.slots' and any(x.name=='build_slot_layout' for x in n.names) for n in ttree.body)
# Read deciding bytes and exact XML, without re-running the estimator/native suites.
control=[]
for mode,expected in [('untouched',(0,7,0,0,0)),('removed',(1,7,2,0,0))]:
 execution=json.loads((O/f'graph-{mode}.execution.json').read_text())
 assert execution['source_before']==execution['source_after'] and execution['source_before']['head']==H
 for key in ['stdout','stderr','junit','replayer']:assert ref(execution[key]['path'])==execution[key]
 xt=ET.parse(O/f'graph-{mode}.xml').getroot();xs=next(xt.iter('testsuite'))
 actual=(execution['exit_code'],int(xs.attrib['tests']),int(xs.attrib['failures']),int(xs.attrib['errors']),int(xs.attrib['skipped']))
 assert actual==expected
 cases=[]
 for c in xt.iter('testcase'):
  f=c.find('failure');cases.append({'name':c.attrib['name'],'outcome':'FAIL' if f is not None else 'PASS','message':None if f is None else f.attrib.get('message'),'complete_failure_body':None if f is None else f.text})
 stdout=(O/f'graph-{mode}.stdout.txt').read_text();last=json.loads(stdout.splitlines()[-1]);assert last['actual_pytest_exit_code']==execution['exit_code']
 warnings=[x for x in stdout.splitlines() if 'Warning:' in x and not x.startswith('{')]
 assert len(warnings)==2 and all(('AssertRewriteWarning' in x or 'PytestConfigWarning' in x) for x in warnings)
 assert not any(token in '\n'.join(x for x in stdout.splitlines() if not x.startswith('{')) for token in ['Prometheus bootstrap failed','Address already in use'])
 control.append({'mode':mode,'execution':execution,'actual_counts':{'tests':7,'PASS':7-int(xs.attrib['failures']),'FAIL':int(xs.attrib['failures']),'ERROR':0,'SKIP':0},'testcases':cases,'warning_lines':warnings,'observed_origin_count':len(last['origins']),'source_origins_all_actual_candidate':True,'fresh_reader_scope':last['fresh_reader_scope']})
summary={'schema':'e02.F.api.combined.source_audit.v1','outcome':'PASS','candidate_sha':H,'candidate_tree':'551d4e760dc1168f6ad8182c9b176f00e94a2281','base_sha':B,'full_changed_path_denominator':10,'component_path_counts':{'graph':6,'benchmark':1,'docs':3},'all_changed_paths':sorted(allpaths),'full_changed_path_bindings':bindings,'full_patch':ref(O/'combined.full.patch'),'docs_author_inputs_reverified_at_current_candidate':docs_inputs,'docs_actual_html_anchors':anchors,'docs_author_native_suite':{'tests':6,'PASS':6,'FAIL':0,'ERROR':0,'SKIP':0,'execution':ref(layout),'origin_role':'author-native evidence independently inspected; no reviewer reexecution claimed'},'docs_author_scoped_build':{'outcome':'PASS','receipt':ref(doc),'scope':'actual inherited MkDocs/plugins; state page only, not full strict docs','full_stream_refs':{'stdout':dr['stdout'],'stderr':dr['stderr']},'html':dr['html'],'original_notice_and_excluded_nav_INFO_preserved':True},'docs_owner_contract':{'internal_rule':contract['public_surface']['internal_rule'],'not_manifest_supported_entrypoints':addresses,'canonical_imports':facades,'native_owner':'polisyos.ir.kernel.slots','native_objects':sorted(exports),'compiler_direct_IR_import':bind(H,trinity),'no_facade_runtime_export_identity_lifecycle_change':True},'graph_property_measurements':control,'b204_independent_review':ref(O/'b204-independent-review.json'),'review_scope':['Canonical private family guard before filtering/reconciliation; unchanged static endpoint/lag guard.','Direct/supplied MethodResult, selected graph/cache/fragments/query reconstruction/prepersist call paths inspected.','ComposeSCMFragments covers typed-model-copy bypass; DTO already refuses unsupported families.','Known reverse/bidirected ADMG normalization retained; PAG projection and other partial/missingness consumer contracts unchanged.','Benchmark only checker changes; full native DID math and all other benchmark AST/fixture/runner remain unchanged.','LA037 docs establish IR ownership and direct compatibility bindings with tracked lifecycle prerequisites.'],'limitations':['No formal finding closure or G authority adjudication.','B214 remains broadly limited; only reconciliation/Compose/Node admission is DAG/ADMG.','Same-process reopenedCAS in these7tests; no new fresh-child claim.','No DoWhy/EconML optional backend/profile run, admitted real data or actual Runtime authority-positive from these probes.','Two original scanner ERROR/-9,103 RuffFAIL and38 static incomplete exports retain original-input scope; no third scanner or P41 exclusion.','No broad docs/native package/installed-suite PASS inferred.']}
(O/'source-audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'source_audit':ref(O/'source-audit.json'),'outcome':'PASS','paths':10,'graph_untouched':control[0]['actual_counts'],'graph_removed':control[1]['actual_counts'],'docs_author_anchors':anchors,'B204':ref(O/'b204-independent-review.json')},indent=2))
