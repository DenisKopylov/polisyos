import argparse, subprocess, pathlib, hashlib, json, datetime
p=argparse.ArgumentParser();p.add_argument("--local",required=True);p.add_argument("--remote-db",required=True);p.add_argument("--remote-ref",required=True);p.add_argument("--out",required=True);a=p.parse_args()
base="0321633c0e6d9a87bccfbbe889a4998934c52dd3";source="03698439abfb1cb59f763397a182d8e0e393d40d"
def git(where,*args):return subprocess.check_output(["git","-C",where,*args])
head=git(a.local,"rev-parse","HEAD").decode().strip();remote=git(a.remote_db,"rev-parse",a.remote_ref).decode().strip();assert head==remote
assert not git(a.local,"status","--porcelain")
commits=git(a.local,"rev-list","--reverse",base+".."+head).decode().splitlines()
lineage=[]
for commit in commits:
 for kind in ["commit","tree"]:
  obj=commit if kind=="commit" else commit+"^{tree}"
  left=git(a.local,"cat-file",kind,obj);right=git(a.remote_db,"cat-file",kind,obj);assert left==right,(commit,kind)
 tree=git(a.local,"rev-parse",commit+"^{tree}").decode().strip();parents=git(a.local,"rev-list","--parents","-n","1",commit).decode().split()[1:];assert parents==git(a.remote_db,"rev-list","--parents","-n","1",commit).decode().split()[1:]
 lineage.append({"commit":commit,"tree":tree,"parents":parents,"commit_sha256":hashlib.sha256(git(a.local,"cat-file","commit",commit)).hexdigest(),"tree_bytes_equal":True})
def blobs(where,requests):
 raw=subprocess.check_output(["git","-C",where,"cat-file","--batch"],input=("\n".join(requests)+"\n").encode());offset=0;out=[]
 for request in requests:
  end=raw.index(b"\n",offset);header=raw[offset:end].decode().split();assert len(header)==3 and header[1]=="blob",(request,header);size=int(header[2]);start=end+1;data=raw[start:start+size];assert raw[start+size:start+size+1]==b"\n";offset=start+size+1;out.append((header[0],data))
 assert offset==len(raw);return out
manifest=[]
for selected in [source,head]:
 paths=git(a.local,"diff","--name-only","--diff-filter=AM",base,selected).decode().splitlines();requests=[selected+":"+path for path in paths];left=blobs(a.local,requests);right=blobs(a.remote_db,requests)
 for path,(lb,ld),(rb,rd) in zip(paths,left,right):
  assert lb==rb and ld==rd,(selected,path);manifest.append({"commit":selected,"path":path,"blob":lb,"bytes":len(ld),"sha256":hashlib.sha256(ld).hexdigest()})
root=pathlib.Path(a.local);leaf=root/"policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/recovery-20261008/B114-rejection-retention";index=json.loads((leaf/"evidence/artifact-index.json").read_text())
for artifact in index["artifacts"]:
 data=(root/artifact["path"]).read_bytes();assert hashlib.sha256(data).hexdigest()==artifact["sha256"] and len(data)==artifact["bytes"]
assert not (pathlib.Path(a.remote_db)/"objects/info/alternates").exists()
result={"schema":"orch04.C11.B114.normal-publication-byte-readback.v1","utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"head":head,"tree":git(a.local,"rev-parse","HEAD^{tree}").decode().strip(),"source":source,"source_tree":git(a.local,"rev-parse",source+"^{tree}").decode().strip(),"remote_ref":a.remote_ref,"remote_db":a.remote_db,"status":"PASS actual remote bytes equal local complete leaf source and packet footprint","lineage":lineage,"source_footprint_count":sum(x["commit"]==source for x in manifest),"final_head_footprint_count":sum(x["commit"]==head for x in manifest),"packet_index_file_count":len(index["artifacts"]),"manifest":manifest,"empty_objects_at_admission":"separate bare init receipt records count0 before fetch; no alternates","limits":"source acceptance/formal G closure/production and portable replay remain separate"}
pathlib.Path(a.out).write_text(json.dumps(result,indent=2)+"\n");print(json.dumps({k:result[k] for k in ["head","tree","status","source_footprint_count","final_head_footprint_count","packet_index_file_count"]}))
