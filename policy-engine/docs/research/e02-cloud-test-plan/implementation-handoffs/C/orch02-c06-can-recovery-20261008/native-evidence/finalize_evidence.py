from pathlib import Path
import json,hashlib,subprocess,xml.etree.ElementTree as ET,gzip,shutil,zipfile,datetime
R=Path('/workspace/orch02-native-c06');E=R/'handoff-evidence'
S={'dfk':{'repo':'/workspace/orch02-c06-dfk','base':'a13f6c1acfe15a6750d71c6e86521f119d794def','head':'cbbfffd367fe283813a8177575d26c0ede8d20c4','tree':'e0ca5462ec6f38f91e4d2ebedf1bf2f18f2c9f99'},'can':{'repo':'/workspace/orch02-c06-can','base':'f00dd7661a8d3329fb1fa1b049decb0d1d2f277b','head':'4901e26841e2be0ae6ef393754abed5cafb1e2d4','tree':'7e73132dd639bf03e40a27dd5f12837d916aeb3f'}}
RUNS={'dfk':['dfk-native','dfk-old-classifier','protocol-native-v3','dfk-census','dfk-census-no-timeout','dfk-build','dfk-rebuilt-wheel','dfk-wheel-install','dfk-wheel-consumer','dfk-rebuilt-install','dfk-rebuilt-consumer','protocol-native','protocol-native-v2'], 'can':['can-native','can-consumer-companions','can-independent-native','can-original-reader','can-no-separators-normalization','can-no-completeness-guard','can-build','can-rebuilt-wheel','can-wheel-install','can-wheel-consumer','can-rebuilt-install','can-rebuilt-consumer']}
COMMON=['build-env-create','build-env-install','consumer-env-create','consumer-env-install']
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def ref(p):b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def git(role,*a):return subprocess.check_output(['git','-C',S[role]['repo'],*a])
def freeze_sources(role):
 s=S[role];assert git(role,'rev-parse','HEAD').decode().strip()==s['head'];assert git(role,'rev-parse','HEAD^{tree}').decode().strip()==s['tree'];status=git(role,'status','--porcelain','-z');assert not status
 paths=git(role,'diff','--name-only','-z',s['base'],s['head']).split(b'\0');rows=[]
 for p in paths:
  if not p:continue
  p=p.decode();b=git(role,'show',s['head']+':'+p);rows.append({'path':p,'blob':git(role,'rev-parse',s['head']+':'+p).decode().strip(),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)})
 return {**s,'status_porcelain_z_hex':status.hex(),'complete_changed_paths':rows}
def bind_origins(role):
 s=S[role];objects={};raw=git(role,'ls-tree','-r','-z',s['head'])
 for rec in raw.split(b'\0'):
  if rec:
   hdr,p=rec.split(b'\t',1);objects[p.decode()]=hdr.split()[2].decode()
 needed={};runrows=[]
 for run in RUNS[role]:
  p=R/run/'origins.json'
  if not p.exists():continue
  j=json.loads(p.read_text());assert j['foreign_origins']==[];rows=[]
  for o in j['origins']:
   origin=Path(o['origin'])
   if str(origin).startswith(s['repo']+'/'):
    rel=str(origin.relative_to(s['repo']));blob=objects[rel];needed[blob]=None;rows.append({**o,'source_path':rel,'git_blob':blob})
   elif '/removals/' in str(origin):
    assert hashlib.sha256(origin.read_bytes()).hexdigest()==o['sha256'];rows.append({**o,'isolated_matched_removal':True})
   elif '/site-packages/' in str(origin):
    continue
   else:raise AssertionError(o)
  if rows:runrows.append({'run':run,'origin_file_denominator':len(j['origins']),'rows':rows})
 if needed:
  b=subprocess.check_output(['git','-C',s['repo'],'cat-file','--batch'],input=('\n'.join(needed)+'\n').encode());off=0
  for oid in needed:
   nl=b.index(b'\n',off);hdr=b[off:nl].split();n=int(hdr[2]);assert hdr[0].decode()==oid;data=b[nl+1:nl+1+n];needed[oid]=hashlib.sha256(data).hexdigest();off=nl+1+n+1
 for run in runrows:
  for o in run['rows']:
   if 'git_blob' in o:assert needed[o['git_blob']]==o['sha256'],o
 out={'source_commit':s['head'],'complete_observed_file_origin_denominators':runrows,'every_nonmutant_observed_source_origin_matches_exact_git_blob':True,'mutant_leaf_bytes_bound_separately':True};put(R/(role+'-source-origin-reconciliation.json'),out)

def wheel_origins(role,label,kind):
 wheel=R/'packages'/role/kind/'policy_engine-0.1.0-py3-none-any.whl';j=json.loads((R/label/'origins.json').read_text());assert not j['foreign_origins'];rows=[]
 with zipfile.ZipFile(wheel) as z:
  for o in j['origins']:
   member=o['origin'].split('/site-packages/',1)[1];sha=hashlib.sha256(z.read(member)).hexdigest();assert sha==o['sha256'];rows.append({**o,'wheel_member':member})
 put(R/label/'wheel-origin-reconciliation.json',{'wheel':str(wheel),'wheel_sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'origin_file_denominator':len(rows),'every_origin_matches_wheel_MEMBER_and_RECORD':True,'record_reference':str(R/'packages'/role/'rebuilt-wheel-manifest.json'),'rows':rows})

def run_receipt(label):
 d=R/label;j=json.loads((d/'command.json').read_text());j['label']=label;j['complete_outputs']=[ref(d/f) for f in ['command.json','stdout.txt','stderr.txt','junit.xml','origins.json','wheel-origin-reconciliation.json'] if (d/f).exists()]
 if (d/'junit.xml').exists():j['junit_suites']=[x.attrib for x in ET.parse(d/'junit.xml').getroot().iter('testsuite')]
 return j

def copy(role,p):
 out=E/role/p.relative_to(R);out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,out);return ref(out)
def compress(role,p):
 out=E/role/(str(p.relative_to(R))+'.gz');out.parent.mkdir(parents=True,exist_ok=True);b=p.read_bytes()
 with out.open('wb') as f:
  with gzip.GzipFile(fileobj=f,mode='wb',mtime=0) as gz:gz.write(b)
 assert gzip.decompress(out.read_bytes())==b;return {'complete_lossless_gzip':ref(out),'decoded_exact':ref(p),'round_trip_verified':True}

for role in S:
 bind_origins(role)
for role,label,kind in [('dfk','dfk-rebuilt-consumer','rebuilt-dist')]:wheel_origins(role,label,kind)
review={'independent_reviewer':'native_c06 direct helper; no children','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_scope':'read-only frozen source lanes; no production edits, source commits, shared-environment installation or integrated G verdict','material_implementation_findings':[],'source_qualified_verdicts':{'DFK':'GO for final cbb parser property and bounded finite census observations; not repository-wide or external legacy retirement','CAN':'GO for final 4901 reader-only profile admission/reconstruction; not overall LA-021 closure'},'specification_review':{'DFK':'Real Git v1 porcelain-z R/C records consume both paths; ordinary M and AM retain following records, independent diff/ls-files oracle, all selected local text reads bounded by finite denominator. Documentation retains ignored/binary/dynamic/external/historical limits.','CAN':'Actual FileSystemCAS producer, full persisted JSON-mode CanonInfo Mapping, fresh reader, separators normalization, max_depth129, Decimal golden bytes and explicit malformed/unsupported/missing-field refusal before get_bytes are exercised. No producer or adapter/Core changes.'},'quality_review':'Native affected tests, independent native protocol/CAS probes, marker-preserving matched removals, exact frozen Git export builds, complete wheel/sdist source-member walks, direct-vs-sdist rebuilt byte identity and RECORD hashes, fresh installed consumer origins establish bounded local behavior. All command/output/JUnit/origin bytes are referenced in split manifests. Source-only AST test is excluded from installed proof.','correctness_review':'No material regression identified in affected bounded properties. Removals discriminate each admitted repair; negatives retain tests/docs/markers. Initial protocol incorrect unstaged-rename read oracle and arbitrary 300-second census timeout were harness failures, preserved and superseded on unchanged source.','decisions_and_limits':[{'owner':'G/C02/Core','status':'HELD','detail':'Raw Core same canon name/version can persist Core-only float_hex/bytes_hex/array_digest tags. Actual CAS examples are admitted by profile, then IR rejects after bytes. Metadata shape/type does not establish tag-set custody; no bypass fix claimed.'},{'owner':'G/C02','status':'HELD','detail':'Historical profile-less stores are explicitly refused before byte read. Deployment/backward-compatibility policy must be decided by owners.'},{'owner':'C02/Core','status':'UNCHANGED','detail':'Non-Core adapter option coercion omits tenant_context/same_input_closure/authority/warnings; unchanged producer/adapter contract outside reader delta.'},{'owner':'G','status':'COMPOSED_RERUN_REQUIRED','detail':'CAN actual native complete observed file-origin denominator 885 compared to G032 has candidate reader IO delta plus loaded foundry/calibration/identifiability older f00 blob aad1abdd89ac8dda43918981bc21f4a9755601a2 vs G blob d0b90fd348a2556b5e23ae8e20409950ad9e712b. Codec/Core/IR/config contour zero delta is not an all-source claim. Candidate-local consumer PASS does not transfer to G composition.'},{'owner':'G/external owners','status':'NOT_ESTABLISHED','detail':'DFK census selects and reads finite local tracked/untracked text only; runtime-generated/nonliteral, ignored/binary, deployed external/historical clients and N/date/window compatibility sunset remain undecided. Package-member checks are separate evidence, not the scanner asserting installed absence.'}], 'source_reviews_pre_native':ref(R/'source-review-prewave.json'),'final_sources':{r:freeze_sources(r) for r in S},'formal_acceptance':'G alone; no integrated acceptance or finding-closure verdict'}
put(R/'independent-final-review.json',review)
for role in S:
 mod=[];zips=[];oversized=[]
 for label in RUNS[role]+COMMON:
  for f in ['command.json','stdout.txt','stderr.txt','junit.xml','origins.json','wheel-origin-reconciliation.json']:
   p=R/label/f
   if p.exists():
    if p.stat().st_size>1000000:zips.append(compress(role,p))
    else:mod.append(copy(role,p))
 shared=['receipt_run.py','pytest_bound.py','pytest.installed.ini','package_export.py','package_inspect.py','finalize_evidence.py','consumer-dependencies.txt','source-review-prewave.json','independent-final-review.json','packages/source-manifest.json','packages/consumer-test-manifest.json','removals/manifest.json',role+'-source-origin-reconciliation.json']
 extra={'dfk':['protocol_probe.py','test_dfk_installed.py','protocol-preflight.json','protocol-matrix-v3/receipt.json','dfk-census-summary.json','handoff-evidence/lossless-deciding-output-manifest.json','dfk-independent-denominator.json'],'can':['test_can_independent.py','can-loaded-G-reconciliation.json']}[role]
 for p in [R/x for x in shared+extra]+list((R/'removals').glob(role+'-*')):
  if p.stat().st_size>1000000:zips.append(compress(role,p))
  else:mod.append(copy(role,p))
 for x in ['archive-manifest.json','rebuilt-wheel-manifest.json']:
  p=R/'packages'/role/x;zips.append(compress(role,p))
 for p in [R/'packages'/role/'source.tar',R/'packages'/role/'tree.raw']+list((R/'packages'/role/'dist').glob('*'))+list((R/'packages'/role/'rebuilt-dist').glob('*')):
  if p.exists():oversized.append(ref(p))
 ar=json.loads((R/'packages'/role/'archive-manifest.json').read_text());re=json.loads((R/'packages'/role/'rebuilt-wheel-manifest.json').read_text())
 manifest={'role':role.upper(),'source':review['final_sources'][role],'verdict':review['source_qualified_verdicts'][role.upper()],'independent_review':ref(R/'independent-final-review.json'),'runs':[run_receipt(x) for x in RUNS[role]+COMMON],'package_closure':{'wheel_member_denominator':len(ar['wheel_members']),'sdist_member_denominator':len(ar['sdist_members']),'all_source_owned_member_bytes_match_frozen_git_archive':ar['all_source_owned_member_bytes_match_frozen_git_archive'],'direct_rebuilt_member_names_and_bytes_equal':re['all_member_names_and_bytes_equal'],'wheel_RECORD_complete_and_hashes_valid':re['wheel_RECORD_complete_and_hashes_valid'],'all_source_owned_wheel_members_bind_exact_git_blobs_count':len(re['all_source_owned_wheel_members_bind_exact_git_blobs']),'retired_DFK_exact_member_prefixes_absent':ar['DFK_retired_exact_member_prefixes_absent'],'no_source_or_editable_overlay':True,'fresh_process_each_install':True},'publishable_moderate_complete_artifacts':mod,'publishable_lossless_complete_artifacts':zips,'oversized_reproducible_raw_artifacts':oversized,'do_not_commit':'source exports, complete build directories, CAS fixtures, dependency environments, source archives/wheels/sdists; raw path@hash preserved, exact build commands reproducible','limits':review['decisions_and_limits']}
 put(R/(role+'-final-manifest.json'),manifest);put(E/role/'final-manifest.json',manifest)
 print(role,len(mod),len(zips),sum(x['bytes'] for x in mod)+sum(x['complete_lossless_gzip']['bytes'] for x in zips))
