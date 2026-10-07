"""Complete read-only immutable519 Git/snapshot/sdist/wheel/site/carrier verification."""
import collections,hashlib,json,pathlib,subprocess,tarfile,threading,time,tomllib,zipfile
OUT=pathlib.Path(__file__).resolve().parent;PACKET=pathlib.Path('/tmp/e02-F-continuation-20261007/foundry/installed-default-resource-forward');ROOT=pathlib.Path('/workspace/e02-F-api-20261006');SHA='519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82';TREE='750d28da94f372848fe6b2db5f88db95b94cb57d'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def h(b):return hashlib.sha256(b).hexdigest()
def ref(p):p=pathlib.Path(p);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':h(b)}
def read(n):return json.loads((PACKET/n).read_text())
start=time.monotonic();config=read('installed-config.json');source=read('source-snapshot-proof.json');author=read('archive-installed-source-bindings.json');carrier=read('carrier-manifest.json');assert config['source_sha']==SHA and config['source_tree']==TREE and git('rev-parse',SHA+'^{tree}').decode().strip()==TREE;entries=[]
for item in git('ls-tree','-rz','--full-tree',SHA).split(b'\0'):
 if item:
  meta,name=item.split(b'\t',1);mode,kind,oid=meta.decode().split();assert kind=='blob' and mode in ['100644','100755'];entries.append((name.decode(),oid,mode))
process=subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
def feed():
 for _,oid,_ in entries:process.stdin.write((oid+'\n').encode())
 process.stdin.close()
thread=threading.Thread(target=feed);thread.start();aggregate=hashlib.sha256();total=0;by_source={};expected={}
for name,oid,mode in entries:
 hdr=process.stdout.readline().decode().split();assert hdr[:2]==[oid,'blob'];raw=process.stdout.read(int(hdr[2]));assert process.stdout.read(1)==b'\n';p=pathlib.Path(config['source_root'])/name;assert p.read_bytes()==raw,name;assert (p.stat().st_mode&0o777)==(0o755 if mode=='100755' else 0o644)
 row={'source':name,'git_blob':oid,'bytes':len(raw),'sha256':h(raw),'mode':mode};by_source[name]=row;aggregate.update((name+'\0'+row['sha256']+'\0'+str(len(raw))+'\n').encode());total+=len(raw)
 if name.startswith(('policy-engine/src/polisyos/','policy-engine/tools/')):
  dest=name.removeprefix('policy-engine/src/').removeprefix('policy-engine/');assert dest not in expected;expected[dest]={k:v for k,v in row.items() if k!='mode'}|{'destination':dest,'role':'tracked_product'}
assert not process.stdout.read();thread.join();assert process.wait()==0;assert len(entries)==source['complete_original_Git_files'] and total==source['complete_original_Git_bytes'] and aggregate.hexdigest()==source['ordered_path_hash_size_aggregate'];product_count=len(expected)
hatch=tomllib.loads(git('show',SHA+':policy-engine/hatch.toml').decode());resources=hatch['build']['targets']['wheel']['force-include'];assert len(resources)==11
for src,dest in resources.items():
 assert dest not in expected;expected[dest]={k:v for k,v in by_source['policy-engine/'+src].items() if k!='mode'}|{'destination':dest,'role':'forced_resource'}
assert {r['destination']:r for r in author['source_bindings']}==expected
# Actual complete sdist bytes and materialized rebuild inputs are independently reread, including generated PKG-INFO.
decoded=read('actual-sdist-decoded-payloads.json');decoded_rows={r['actual_tar_member']:r for r in decoded['members']};assert len(decoded_rows)==len(decoded['members']);seen=set();tar_total=0;tar_count=0;generated=[];by_tar={};prefix=None
with tarfile.open(config['archives']['sdist'],'r|gz') as tar:
 for member in tar:
  rel=pathlib.PurePosixPath(member.name);assert not rel.is_absolute() and '..' not in rel.parts and not member.issym() and not member.islnk() and member.isfile();assert member.name not in seen;seen.add(member.name)
  if prefix is None:prefix=rel.parts[0]
  assert rel.parts[0]==prefix;raw=tar.extractfile(member).read();row=decoded_rows[member.name];assert len(raw)==member.size==row['bytes'] and h(raw)==row['sha256'] and member.mode==row['actual_tar_mode'];materialized=pathlib.Path(decoded['rebuilt_source_root'])/pathlib.Path(*rel.parts[1:]);assert materialized.read_bytes()==raw and (materialized.stat().st_mode&0o777)==member.mode;source_name='policy-engine/'+pathlib.PurePosixPath(*rel.parts[1:]).as_posix()
  if source_name in by_source:
   current=by_source[source_name];assert current['bytes']==len(raw) and current['sha256']==h(raw),source_name
  else:generated.append(member.name)
  by_tar[source_name]={'bytes':len(raw),'sha256':h(raw)};tar_total+=len(raw);tar_count+=1
assert seen==set(decoded_rows) and tar_count==decoded['actual_decoded_regular_members'] and tar_total==decoded['actual_decoded_regular_bytes'];assert generated==[prefix+'/PKG-INFO'];assert set('policy-engine/'+p for p in resources)<=set(by_tar)
for row in expected.values():assert by_tar[row['source']]=={'bytes':row['bytes'],'sha256':row['sha256']}
archives={}
for kind,path in config['archives'].items():archives[kind]=ref(path);assert archives[kind]==author['archives'][kind]
for kind in ['wheel','rebuilt_wheel']:
 with zipfile.ZipFile(config['archives'][kind]) as wheel:
  all_names=wheel.namelist();assert len(all_names)==len(set(all_names));names={n for n in all_names if n.startswith(('polisyos/','tools/')) and not n.endswith('/')};assert names==set(expected)
  for name,row in expected.items():raw=wheel.read(name);assert len(raw)==row['bytes'] and h(raw)==row['sha256']
assert archives['wheel']['sha256']==archives['rebuilt_wheel']['sha256'];sites={}
for kind,site_name in config['sites'].items():
 site=pathlib.Path(site_name)
 for dest,row in expected.items():raw=(site/dest).read_bytes();assert len(raw)==row['bytes'] and h(raw)==row['sha256'],(kind,dest)
 actual={p.relative_to(site).as_posix() for ns in ['polisyos','tools'] for p in (site/ns).rglob('*.py')};assert actual=={n for n in expected if n.endswith('.py')};pths=[]
 for p in sorted(site.glob('*.pth')):
  body=p.read_text();assert str(config['source_root']) not in body and 'polisyos' not in body;pths.append(ref(p)|{'literal_contents':body})
 assert (site/'e02_readonly_dependencies.pth').read_text()==config['dependency_site']+'\n';cwd=PACKET/(kind+'-consumer');assert not (cwd/'src').exists()
 for row in carrier['files']:
  raw=(cwd/row['path'].removeprefix('policy-engine/')).read_bytes();assert len(raw)==row['bytes'] and h(raw)==row['sha256']
  if row.get('git_sha'):assert raw==git('show',SHA+':'+row['path']) and git('rev-parse',SHA+':'+row['path']).decode().strip()==row['blob']
  else:assert raw==pathlib.Path(row['original_path']).read_bytes()
 sites[kind]={'complete_declared_product_resource_files':len(expected),'complete_actual_python_files':len(actual),'carrier_files':len(carrier['files']),'neutral_src_absent':True,'pth':pths}
command_records=read('setup-command-records.json')
for row in command_records:
 if 'exit_code' in row:assert row['exit_code']==0
 for key in ['stdout','stderr']:
  if key in row:assert ref(row[key]['path'])==row[key]
result={'source_sha':SHA,'source_tree':TREE,'custody_verdict':'PASS','consumer_native_verdict':'Notmeasuredbythisreplayer;separateactualnative/negative/probeproof','source_snapshot':{'complete_Git_files':len(entries),'bytes':total,'aggregate':aggregate.hexdigest(),'shared_inode_policy':source['shared_inode_policy']},'complete_sdist':{'actual_members':tar_count,'actual_decoded_bytes':tar_total,'all_rebuilt_payloads_exact':True,'generated_metadata_members':generated},'product_files':product_count,'forced_resources':len(resources),'declared_product_resource_files':len(expected),'resources':resources,'archives':archives,'sites':sites,'setup_command_record_count':len(command_records),'complete_setup_outputs_rebound':True,'input_refs':[ref(PACKET/n) for n in ['installed-config.json','source-snapshot-proof.json','archive-installed-source-bindings.json','actual-sdist-decoded-payloads.json','carrier-manifest.json','setup-command-records.json','catalog-expected.json','profile-expected.json']],'seconds':time.monotonic()-start,'new_builder_or_site_mutation':False};(OUT/'custody-review.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
