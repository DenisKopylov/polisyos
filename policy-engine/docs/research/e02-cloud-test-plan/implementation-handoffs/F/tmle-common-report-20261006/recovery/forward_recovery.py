import hashlib, json, os, pathlib, subprocess, time
ROOT=pathlib.Path("/workspace/e02-F-tmle-20261006")
OUT=pathlib.Path(__file__).parent
BASE="d23f004d4f0ed442bc00dae634ed73c6b80275d5"
TARGET="47a2ff90186628afafa4c01ecf7158325b0026fc"
TARGET_TREE="d7f5e47193b7049fd06b7a59e0a759b796e0934a"
commands=[]
def run(args, input=None):
 p=subprocess.run(args,cwd=ROOT,input=input,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 n=len(commands); (OUT/f"command-{n}.stdout.txt").write_bytes(p.stdout); (OUT/f"command-{n}.stderr.txt").write_bytes(p.stderr)
 commands.append({"argv":args,"cwd":str(ROOT),"exit_code":p.returncode,"stdout":str(OUT/f"command-{n}.stdout.txt"),"stderr":str(OUT/f"command-{n}.stderr.txt")})
 (OUT/"forward-commands.json").write_text(json.dumps(commands,indent=2)+"\n")
 assert p.returncode==0,(args,p.stderr.decode(errors="replace"))
 return p.stdout
def git(*args, input=None): return run(["git",*args],input)
assert git("rev-parse","HEAD").decode().strip()==BASE
assert not git("diff","--cached","--name-only")
snapshot=json.loads((OUT/"snapshot.json").read_text())
for row in snapshot["partial_entries"]:
 data=pathlib.Path(row["snapshot"]).read_bytes()
 assert len(data)==row["bytes"] and hashlib.sha256(data).hexdigest()==row["sha256"]
 assert (ROOT/row["path"]).read_bytes()==data, row["path"]
paths=snapshot["target_delta_paths"]
entries={}
for record in git("ls-tree","-rz",TARGET).split(b"\0"):
 if not record:continue
 info,name=record.split(b"\t",1); mode,kind,blob=info.decode().split();entries[name.decode()]=(mode,kind,blob)
written=[]
for name in paths:
 mode,kind,blob=entries[name]
 assert kind=="blob" and mode in ("100644","100755"),(name,mode,kind)
 data=git("cat-file","blob",blob)
 p=ROOT/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(data); p.chmod(0o755 if mode=="100755" else 0o644)
 assert p.read_bytes()==data
 written.append({"path":name,"blob":blob,"mode":mode,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()})
pathspec=OUT/"target-paths.nul";pathspec.write_bytes(b"\0".join(x.encode() for x in paths)+b"\0")
git("add",f"--pathspec-from-file={pathspec}","--pathspec-file-nul")
assert git("write-tree").decode().strip()==TARGET_TREE
status=git("status","--porcelain=v1","-z","-uall")
for entry in status.split(b"\0"):
 if entry:assert entry[3:].decode() in set(paths),entry
message=OUT/"recovery-commit-message.txt";message.write_text("Recover interrupted admitted root merge forward\n\nMaterialize the exact 47a2ff90186628afafa4c01ecf7158325b0026fc target tree after disk exhaustion interrupted checkout. Preserve original partial bytes and command receipts in /tmp. No reset, deletion, or history rewrite.\n")
git("commit","-F",str(message))
recovery=git("rev-parse","HEAD").decode().strip();assert git("rev-parse","HEAD^{tree}").decode().strip()==TARGET_TREE
git("merge","--no-ff","--no-edit",TARGET)
merged=git("rev-parse","HEAD").decode().strip();assert git("rev-parse","HEAD^{tree}").decode().strip()==TARGET_TREE
parents=git("rev-list","--parents","-n","1","HEAD").decode().strip().split()[1:]
assert parents==[recovery,TARGET],parents
assert not git("status","--porcelain=v1","-uall")
report={"base":BASE,"target":TARGET,"target_tree":TARGET_TREE,"recovery_commit":recovery,"merge_commit":merged,"parents":parents,"written":written,"snapshot":str(OUT/"snapshot.json"),"commands":str(OUT/"forward-commands.json"),"clean":True,"no_deletions":True}
(OUT/"forward-recovery.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps({k:v for k,v in report.items() if k!="written"}))
