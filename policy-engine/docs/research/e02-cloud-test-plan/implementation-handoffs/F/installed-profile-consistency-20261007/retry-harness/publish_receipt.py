"""Publish one receipt-only packet; preserve exact moderate deciding bytes."""
from pathlib import Path
import gzip, hashlib, json, shutil, subprocess, xml.etree.ElementTree as ET

OWN = Path('/workspace/e02-F-fry-20261006')
OLD = Path('/tmp/e02-F-profile-consistency-20261007/installed')
NEW = Path('/dev/shm/e02-F-profile-consistency-installed')
BASE = NEW/'candidate-wheel'
SOURCE = '852cc3707bfc7dee132ec07a9ed5adcb5911fdf2'
TREE = '52fb13e9e12d80e4b1af5580f61d15310535e5e8'
SLICE_BASE = '2c09571eb9e9efdb91c09b3b4871a49f4c013c1d'
CARRIER_BASE = 'defa506dfbe226fbbdbdf7722ae84c03828e181b'
REL = Path('policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F')
PACKET_REL = REL/'installed-profile-consistency-20261007'
PACKET = OWN/PACKET_REL
HANDOFF_REL = REL/'installed-profile-consistency-20261007.json'

def git(*args):
    return subprocess.check_output(['git','-C',str(OWN),*args],text=True).strip()
assert git('branch','--show-current')=='codex/e02-F-fry-20261006'
assert git('rev-parse','HEAD')==CARRIER_BASE
assert not git('status','--porcelain')
assert git('rev-parse',SOURCE+'^{tree}')==TREE
assert not PACKET.exists() and not (OWN/HANDOFF_REL).exists()
PACKET.mkdir(parents=True)

sources = []
# Existing tracked source/test carriers are cited by path@SHA, never copied.
for path in OLD.glob('*.py'):
    sources.append((path,Path('original-harness')/path.name))
for name in ('installed-plan.json','importer.stdout.txt','importer.stderr.txt',
             'admission-resume-root-tool.json','admission-resume-root-tool.stderr.txt',
             'admission-ownlane.initial-tool-output.txt','admission-ownlane.initial-attempt.json',
             'prepare.stdout.txt','prepare.stderr.txt'):
    sources.append((OLD/name,Path('original-setup')/name))
for path in (OLD/'candidate-wheel').iterdir():
    if path.is_file() and path.suffix in {'.json','.txt','.xml'}:
        sources.append((path,Path('original-wheel')/path.name))
for path in NEW.iterdir():
    if path.is_file() and path.suffix in {'.json','.txt','.py'}:
        sources.append((path,Path('retry-harness')/path.name))
for path in BASE.iterdir():
    if path.is_file() and path.suffix in {'.json','.txt','.xml'}:
        sources.append((path,Path('retry-wheel')/path.name))
for directory in ('fresh-profile','fresh-profile-corrected'):
    for path in (BASE/directory).rglob('*'):
        if path.is_file():
            sources.append((path,Path('retry-wheel')/directory/path.relative_to(BASE/directory)))
for directory in ('test_requested_pag_reconciliat0','test_requested_pag_reconciliat1',
                  'test_no_reconciliation_request0'):
    for path in (BASE/'native-pytest-tmp'/directory).rglob('*'):
        if path.is_file():
            sources.append((path,Path('native-report-CAS')/directory/path.relative_to(BASE/'native-pytest-tmp'/directory)))
rows=[]
bindings={}
for path,relative in sources:
    raw=path.read_bytes()
    # Large full origin/source-site observations and CAS .blob remain lossless,
    # without copying environments, archives or already tracked source views.
    compress=len(raw)>80000 or relative.suffix=='.blob'
    stored=relative.with_name(relative.name+'.lossless.gz') if compress else relative
    destination=PACKET/stored
    destination.parent.mkdir(parents=True,exist_ok=True)
    payload=gzip.compress(raw,mtime=0) if compress else raw
    destination.write_bytes(payload)
    row={'input_path':str(path),'path':(PACKET_REL/stored).as_posix(),
         'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest(),
         'encoding':'gzip' if compress else 'identity',
         'decoded_bytes':len(raw),'decoded_sha256':hashlib.sha256(raw).hexdigest()}
    assert (gzip.decompress(destination.read_bytes()) if compress else destination.read_bytes())==raw
    rows.append(row);bindings[str(path)]=row
manifest={'schema':'policyos.e02.output_transport.v1','source_sha':SOURCE,'source_tree':TREE,
          'scope':'Complete moderate installed deciding outputs and synthetic CAS; no product source copies, environments or wheel archive copies.',
          'files':rows,'files_count':len(rows),'stored_bytes':sum(r['bytes'] for r in rows),
          'decoded_bytes':sum(r['decoded_bytes'] for r in rows),
          'unavailable_initial_native':'Original /tmp native stdout and JUnit0B after capture ENOSPC; actual native exit and complete streams unknown, ERROR/incomplete.',
          'retained_external_archive':json.loads((OLD/'candidate-wheel/pre-native-custody.json').read_text())['wheel']}
(PACKET/'outputs.json').write_text(json.dumps(manifest,indent=2)+'\n')

def output(path):
    return bindings[str(path)]['path']
checks=[]
for directory,names in ((OLD/'candidate-wheel',('uv-version','build-wheel','create-env','install-wheel','collection','environment','pre-custody')),
                        (BASE,('collection-retry','environment-retry','pre-custody-retry','native-retry','fresh-profile','fresh-profile-corrected','removal','post-custody'))):
    for name in names:
        record_path=directory/(name+'.execution.json')
        record=json.loads(record_path.read_text())
        state='PASS' if record['exit_code']==0 else ('FAIL' if name=='removal' else 'ERROR')
        checks.append({'command':record['argv'],'target_sha':SOURCE,
                       'environment':{'cwd':record['cwd'],**record['environment'],'PYTHONPATH':'absent'},
                       'input_closure':('One expected retained-marker runtime consistency removal; family/static checks and all metadata/source bytes retained' if name=='removal' else
                                        'Child harness serializer ERROR before child launch; actual JobResult issues are dict values' if name=='fresh-profile' else
                                        'Exact frozen source-wheel and SHA-bound affected test/helper carriers; no source product PYTHONPATH'),
                       'outcome':state,'raw_exit_code':record['exit_code'],
                       'seconds':record['seconds'],'maxrss_kib':record.get('maxrss_kib'),
                       'output':output(record_path)})
checks.insert(7,{'command':['python3',str(OLD/'capture_installed.py'),'native',str(OLD/'launch_affected_installed.py'),str(OLD/'candidate-wheel/installed-config.json'),'native'],
                 'target_sha':SOURCE,'environment':'Original Python3.14 source-wheel site, isolated mode, exporter port9476; /tmp reached ENOSPC.',
                 'input_closure':'Same17 selectors; complete native output/exit unavailable after capture failed writing stdout and JUnit remained0B.',
                 'outcome':'ERROR','execution_state':'incomplete','raw_native_exit_code':'unknown',
                 'output':output(NEW/'storage-relocation-and-incomplete-attempt.json')})
checks.extend([
    {'command':None,'target_sha':SOURCE,'environment':'Rebuilt-sdist installed profile not built/replayed',
     'input_closure':'No candidate852 rebuilt-sdist archive/site; historical51991/91 and4ee wheel16 are separate sources.',
     'outcome':'UNRUN','output':'No rebuilt-sdist qualification for852.'},
    {'command':None,'target_sha':SOURCE,'environment':'Application Python3.14; inprocess DoWhy/EconML markers remain excluded.',
     'input_closure':'No optional inprocess estimator/backend or real Runtime/authority admission requested by this narrow graph/report scope.',
     'outcome':'UNRUN','output':'No optional backend, institutional/scientific authority or B56 shared admission positive claimed.'}
])
native=json.loads((BASE/'native-proof.json').read_text())
native_suites=list(ET.parse(BASE/'native-junit.xml').getroot().iter('testsuite'))
assert sum(int(s.get('tests')) for s in native_suites)==len(native['collected_ids'])
assert all(s.get(k)=='0' for s in native_suites for k in ('failures','errors','skipped'))
removal_root=ET.parse(BASE/'removal-junit.xml').getroot()
assert len(removal_root.findall('.//testcase'))==1 and len(removal_root.findall('.//failure'))==1
assert not removal_root.findall('.//error') and not removal_root.findall('.//skipped')
child=json.loads((BASE/'fresh-profile-corrected/fresh-reader-proof.json').read_text())
bridge=json.loads((BASE/'fresh-profile-corrected/fresh-bridge-proof.json').read_text())
assert child['outcome']=='PASS' and child['reader_pid']!=child['parent_pid'] and child['isolated']==1
assert bridge['retagged_rejection']['node_status']=='fail' and not bridge['retagged_rejection']['has_reconciled_ref']
assert bridge['retagged_rejection']['method_result_ref'] is None
custody=json.loads((BASE/'post-run-custody.json').read_text())
assert custody['outcome']=='PASS'
implementation_commits=['ba5fc93aa687eea32973374418a44eae9503a7d0',
                        'd3dfee2558207f4e455730ff96232fc797e78c30',
                        '8a5539cf4874da26c58caa14ca3f22fa0baccf2b',
                        'a175846e457309c1f5ec8887d9ca0075ebeb8824',
                        '3ead92349f5837016f9ad6d5b61b3a7b1d60ace8']
external_paths=git('diff','--name-only',SLICE_BASE,SOURCE).splitlines()
changed_paths=[(PACKET_REL/p.relative_to(PACKET)).as_posix() for p in PACKET.rglob('*') if p.is_file()]+[HANDOFF_REL.as_posix()]
receipt={
 'schema':'policyos.e02.implementation_handoff.v1','unit':'F','slice':'installed-profile-consistency-20261007',
 'closure_ids':[],'related_finding_ids':['B214'],'bundle_ids':['GRF-03'],
 'slice_base_sha':SLICE_BASE,'implementation_commits':implementation_commits,
 'candidate_sha':SOURCE,'candidate_tree_sha':TREE,'branch':'codex/e02-F-fry-20261006',
 'pull_request':'https://github.com/DenisKopylov/polisyos/pull/65',
 'own_carrier_base_sha':CARRIER_BASE,'role':'Receipt-only carrier; external root852 product history is not merged or replayed as a cumulative owner patch.',
 'canonical_writers':{'source_guard':'F root','discovery_report':'F direct discovery helper','installed_qualification':'F direct installed helper'},
 'changed_paths':changed_paths,'external_code_test_companion_footprint':external_paths,
 'baseline_cells':['F08-P048'],'baseline_grade':'Importer PASS; transfer/navigation only, raw archives0; no baseline PASS promoted.',
 'checks':checks,
 'property':{
  'statement':'The actual installed reconciliation MethodJob/Node refuses known reserved MGraph profile contradictions before publication while supported cleanADMG survives; requested unsupported PAG reconciliation retains its graph and a consumed report limitation.',
  'runtime_path':['Frozen852 source-wheel and fresh installed Python3.14 -I site',
                  'Actual registered ReconcileCausalGraph MethodJob and direct/supplied/selected Node intake',
                  'Selected graph CAS plus actual UnifiedCausalDiscovery declared report slot CAS',
                  'Fresh FileSystemCAS report/model readers and one differentPID isolated reader'],
  'surface':'Existing MethodJob declared slots, Node error/artifact surface, DiscoveryPipelineReport warnings/metadata and fresh graph reader; no new authority subsystem.',
  'proxy_divergence':'ADMG tag and resolved endpoints can hide genuine reserved MGraph metadata; with only consistency guard removed, the real job succeeds and the maintained refusal assertion fails. Source metadata/markers/family/static checks remain.',
  'oracle':'Actual build_mgraph/extract_mgraph_metadata contract for genuine originalMGraph; independent literal Y→X and X↔Y relation oracle; native JAX partialcorr PC produces retainedPAG and real report CAS consumers assert prior/hint/no-request distinctions.',
  'negative_controls':[output(BASE/'removal.execution.json')],
  'scientific_scope':'Synthetic DATA confidence0.9 is cutoff support only; no empirical confidence, missingness law identification or real-data authority proof.'},
 'predicate_basis':'recomputed','capability_state_or_finding_state':'Bounded installed source-wheel property PASS with one expected removal FAIL. No finding closure, G code acceptance or whole-head PASS.',
 'profile':{'wheel':manifest['retained_external_archive'],'source_site':str(OLD/'candidate-wheel/wheel-env/lib/python3.14/site-packages'),
            'relocated_site':str(BASE/'wheel-env/lib/python3.14/site-packages'),
            'relocation':'Lossless active site/carrier copy to writable SHM; old archive/site/attempt retained,3464bytes identities equal; no rebuild or deletion.',
            'native_census':{'passed':len(native['collected_ids']),'failed':0,'error':0,'skipped':0,'pytest_warnings':1},
            'removal_census':{'expected_failed':1,'error':0,'skipped':0,'pytest_warnings':2,'detection':'PASS'},
            'warning_denominator':'Native1 UnknownMarkWarning; control2 UnknownMark/AssertRewrite warnings and legacy_method_adapter_ref in raw job. No warning suppression or inherited14 runtime warning claim.',
            'distinct_child':{'parent_pid':child['parent_pid'],'reader_pid':child['reader_pid'],'isolated':1,
                              'child_owned_origins':len(child['product_origins']),'parent_owned_origins':len(bridge['product_origins'])},
            'native_owned_origins':len(native['product_origins']),'origin_violations':native['origin_violations'],
            'full_source_wheel_site_files':custody['complete_candidate_source_wheel_site_files'],
            'actual_python_files':custody['actual_python_files'],'metrics_port':'9476'},
 'output_manifest':(PACKET_REL/'outputs.json').as_posix(),
 'limitations_and_next_owner':[
  'Original /tmp17 attempt ERROR/incomplete after ENOSPC: native output/exit unavailable; never productFAIL/PASS. One same-source affected retry on writable SHM has complete outputs.',
  'Initial child harness ERROR serializing dict JobResult issues before child launch; corrected serializer/unusedCAS directory only, no product source change or17 rerun.',
  '852 rebuilt-sdist UNRUN; old51991/91 and4ee16/fresh-reader receipts retain their own source/input scope.',
  'Python3.14 inprocess DoWhy/EconML UNRUN; real selected Python3.12 worker unchanged and not rerun here.',
  'Known reserved MGraph contract consistency only; no classifier from node names, universal metadata ontology, PAG completion/identification or general temporal authority.',
  'B214 broader partial/completion authority remains deferred A/C/F; B56 actual Runtime/Scientist shared admission/workload roster deferred; no second scheduler or quotas.',
  'G alone accepts code/findings and performs composed integration freeze replay; formal closures0 not changed.',
  'Historical scannerERROR/-9, RuffFAIL103, public-surfaceFAIL38 and P41not_established are not cleared by this installed packet.',
  'Wheel archive/envs and incomplete native fixtures remain local exact locators; full moderate deciding outputs/toyCAS are committed. No cleanup or permanent deletion.'
 ]
}
(OWN/HANDOFF_REL).write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'receipt':HANDOFF_REL.as_posix(),'source':SOURCE,'tree':TREE,
                  'manifest_files':len(rows),'stored_bytes':manifest['stored_bytes'],
                  'decoded_bytes':manifest['decoded_bytes'],'native':len(native['collected_ids']),
                  'control_expected_fail':1,'child':'PASS','changed_receipt_paths':len(changed_paths)}))
