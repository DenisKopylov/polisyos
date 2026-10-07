from __future__ import annotations
import hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path('/workspace/e02-F-closeout-20261006')
SCRATCH=Path('/tmp/e02-F-continuation-20261007')
OUT=Path(__file__).resolve().parent
PREFIX='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-closeout-20261007'

def digest(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def byte_ref(path):return {'original_path':str(path),'bytes':path.stat().st_size,'sha256':digest(path)}
def git_digest(ref,path):
 process=subprocess.Popen(['git','-C',str(ROOT),'show',f'{ref}:{path}'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 total=0;sha=hashlib.sha256()
 while chunk:=process.stdout.read(1<<20):total+=len(chunk);sha.update(chunk)
 stderr=process.stderr.read();exit=process.wait();assert exit==0,(ref,path,stderr)
 return total,sha.hexdigest()

groups={}
selection_inputs=[]
selection_rows={}
for rel in ['economics/root-quality-review','economics/root-companion-review','fit-tmle/root-economic-companion-review','cau/root-current35-review']:
 folder=SCRATCH/rel;input=folder/'transfer-selection.json';obj=json.loads(input.read_bytes());selection_inputs.append(byte_ref(input));rows=obj.get('files') if isinstance(obj.get('files'),list) else obj['items'];selection_rows[rel]=rows
 selected=[]
 for item in rows:
  p=Path(item['path']);p=p if p.is_absolute() else folder/p;observed=byte_ref(p)
  assert observed['bytes']==item['bytes'] and observed['sha256']==item['sha256'],(p,item,observed)
  selected.append(p)
 selected.append(input);groups[rel]=selected
for rel in ['root-integration','root-quality']:
 groups[rel]=sorted(p for p in (SCRATCH/rel).rglob('*') if p.is_file())
# Resolve exact Git-show duplicates from complete retained command tables.  This
# binds originals, not guessed shell-equivalent reconstructions.
known_git={}
for rel in ['economics/root-quality-review','economics/root-companion-review']:
 folder=SCRATCH/rel;commands=json.loads((folder/'commands.json').read_bytes())
 for cmd in commands:
  argv=cmd.get('argv',[]);stdout=cmd.get('stdout')
  if not isinstance(stdout,dict) or 'path' not in stdout:continue
  if len(argv)==3 and argv[:2]==['git','show'] and re.fullmatch(r'[0-9a-f]{40}:.+',argv[2]):
   ref,path=argv[2].split(':',1);p=folder/stdout['path'];n,sha=git_digest(ref,path)
   if p.is_file() and p.stat().st_size==n and digest(p)==sha:
    known_git[str(p)]={'git_ref':ref,'path':path,'bytes':n,'sha256':sha,'git_blob':subprocess.check_output(['git','-C',str(ROOT),'rev-parse',f'{ref}:{path}'],text=True).strip(),'role':'Exact already-published immutable Git bytes; original reviewer stdout is byte-equal, no duplicate transport.'}
# Four current scoped fragment fixtures are exact source blobs.
for p in sorted((SCRATCH/'root-quality/fragments').glob('*.toml')):
 path='policy-engine/release-fragments/unreleased/'+p.name;ref='b5a421d83336e0b50ad9a6747f3f7d041d4c1b5a';n,sha=git_digest(ref,path)
 assert p.stat().st_size==n and digest(p)==sha
 known_git[str(p)]={'git_ref':ref,'path':path,'bytes':n,'sha256':sha,'role':'Exact source fragment input, not copied into transport.'}
p=SCRATCH/'root-integration/cau-publication-primary.json';ref='4d8eaec43d09d9c7df3a2ac8bd244e4d132d03f9';path='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/original35-independent-criterion-review-20261007.json';n,sha=git_digest(ref,path);assert p.stat().st_size==n and digest(p)==sha
known_git[str(p)]={'git_ref':ref,'path':path,'bytes':n,'sha256':sha,'role':'Already published owner primary; exact bytes referenced once.'}
# Existing Git rows from review selections retain exact pointer semantics.  A
# pointer-only row is never converted into a fabricated full body binding.
existing_declared=[]
for rel in ['fit-tmle/root-economic-companion-review']:
 obj=json.loads((SCRATCH/rel/'transfer-selection.json').read_bytes())
 for row in obj.get('existing_git_files',[]):
  if 'bytes' in row and 'sha256' in row:
   n,sha=git_digest(row['git_ref'],row['path']);assert n==row['bytes'] and sha==row['sha256']
  existing_declared.append(row)
logical=[];unique={};aliases=[];existing=[]
# Root owns actual root-output custody first, so reviewer duplicates point to
# root's deciding stream. All source relative directories remain collision-safe.
order=['root-integration','root-quality','economics/root-quality-review','economics/root-companion-review','fit-tmle/root-economic-companion-review','cau/root-current35-review']
for group in order:
 for p in groups[group]:
  binding=byte_ref(p);source_relative=p.relative_to(SCRATCH).as_posix()
  row={'group':group,'source_relative_path':source_relative,**binding}
  if str(p) in known_git:
   row.update(disposition='existing_git',existing_git=known_git[str(p)]);existing.append(row);logical.append(row);continue
  key=(binding['bytes'],binding['sha256'])
  if key in unique:
   row.update(disposition='alias',canonical_original_path=unique[key]['original_path'],canonical_source_relative_path=unique[key]['source_relative_path']);aliases.append(row);logical.append(row);continue
  compression='gzip' if p.name=='invocation-full.json' or p.suffix in {'.patch','.diff'} or binding['bytes']>=1_000_000 else 'identity'
  target=f'{PREFIX}/companions/{source_relative}'+('.gz' if compression=='gzip' else '')
  role=('Complete actual root merge/input custody; full history may embed already-published scientific receipts. Custody bytes do not establish a new estimator/consumer PASS.' if group=='root-integration' and p.suffix in {'.patch','.diff'} else 'Complete unique deciding observation, execution, replayer, history/checkpoint or owner packet; original outcome retained.')
  row.update(disposition='transport',encoding=compression,target_path=target,role=role);unique[key]=row;logical.append(row)
future=[{'id':'new-final-root-quality','status':'UNRUN','git_ref':None,'path':None,'reason':'New source/resource fix has not frozen with exact final quality receipt; append only after publication and byte readback.'},{'id':'new-final-installed-composition','status':'UNRUN','git_ref':None,'path':None,'reason':'Repaired actual wheel/sdist final composition receipt not available yet; no future SHA or pass carry.'},{'id':'packaged-resource-owner-receipt','status':'UNRUN','git_ref':None,'path':None,'reason':'Root assigned canonical Graph author. Reference author published resource proposal/diagnostics/own review instead of duplicate transfer. Existing FIT resource proposal review/selection and Graph diagnosis are not copied by this root transport.'}]
obj={'schema':'policyos.e02.root_transport_draft.v1','draft':True,'root_writes_performed':False,'science_tests_rerun':False,'source_window':{'observed_root_head':'d8334672f44d24dd32113264f96ca3f7954dace4','observed_root_tree':'a68dbc3ecf4ccf9a5a59fa4b830464e32d81dd8f','historical_product_source':'b5a421d83336e0b50ad9a6747f3f7d041d4c1b5a','historical_product_tree':'055871c409ce72e6a29619b235698aa45a6844d4','meaning':'These are immutable observed earlier source identities; draft is not final new resource composition acceptance.'},'primary_target':'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-closeout-20261007.json','artifact_transports_target':f'{PREFIX}/artifact-transports.json','selection_inputs':selection_inputs,'logical_files':logical,'existing_declared_git_references':existing_declared,'pending_extensions':future,'policy':{'full_deciding_output':'User explicitly requires complete moderate raw outputs and lossless full171603690-byte invocation output. This overrides excerpt-only/ignored-raw guidance; raw files stay local unchanged. No deletion, history rewrite or source reformat.','duplication':'Direct already-published Git blobs are referenced; exact-byte duplicates alias one stored complete byte stream. Actual root merge/history diffs are preserved gzip custody even if they contain earlier published receipt content. Unique reviewer batch audit streams remain complete.','proof':'Current/historical FAIL,ERROR,UNRUN remain exact. d833 current35 review is historical observed GO and is not new final-ledger adoption or G authority. No scientific old-wave pass carry from custody.','privacy':'Only already-existing bounded repo/review/source paths and outputs selected. No full environment secrets are added. No sanitation; any discovered credential/query concern must be declared and block that entry separately.','streaming':'Publisher uses1MiB streaming blocks, deterministic gzip timestamp0 and decoded SHA256 verification; no171MB JSON parse or data reconstruction.'},'counts':{'logical_files':len(logical),'unique_transport_files':sum(r['disposition']=='transport' for r in logical),'aliases':len(aliases),'existing_git_files':len(existing),'selected_source_bytes_including_aliases':sum(r['bytes'] for r in logical),'unique_raw_transport_bytes':sum(r['bytes'] for r in logical if r['disposition']=='transport')}}
(OUT/'selection-draft.json').write_text(json.dumps(obj,indent=2)+'\n')
print(json.dumps({'selection':byte_ref(OUT/'selection-draft.json'),'counts':obj['counts'],'validated_input_selections':len(selection_inputs),'existing_source_locator_count':len(known_git),'pending_extensions':future},indent=2))
