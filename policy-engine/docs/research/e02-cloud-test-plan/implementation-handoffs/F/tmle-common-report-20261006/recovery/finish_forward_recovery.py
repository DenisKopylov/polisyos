import hashlib,json,pathlib,subprocess
ROOT=pathlib.Path("/workspace/e02-F-tmle-20261006"); OUT=pathlib.Path(__file__).parent
BASE="d23f004d4f0ed442bc00dae634ed73c6b80275d5"; TARGET="47a2ff90186628afafa4c01ecf7158325b0026fc"; TREE="d7f5e47193b7049fd06b7a59e0a759b796e0934a"
commands=[]
def run(args):
 p=subprocess.run(args,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE);n=len(commands)
 for key,data in (("stdout",p.stdout),("stderr",p.stderr)):(OUT/f"finish-{n}.{key}.txt").write_bytes(data)
 commands.append({"argv":args,"cwd":str(ROOT),"exit_code":p.returncode,"stdout":str(OUT/f"finish-{n}.stdout.txt"),"stderr":str(OUT/f"finish-{n}.stderr.txt")});(OUT/"finish-commands.json").write_text(json.dumps(commands,indent=2)+"\n")
 assert p.returncode==0,(args,p.stderr.decode(errors="replace"));return p.stdout
def git(*args):return run(["git",*args])
assert git("rev-parse","HEAD").decode().strip()==BASE
snapshot=json.loads((OUT/"snapshot.json").read_text());paths=snapshot["target_delta_paths"];pathset=set(paths)
assert all(x.decode() in pathset for x in git("diff","--cached","--name-only","-z").split(b"\0") if x)
entries={}
for row in git("ls-tree","-rz",TARGET).split(b"\0"):
 if row:
  info,name=row.split(b"\t",1); mode,kind,blob=info.decode().split();entries[name.decode()]=(mode,kind,blob)
written=[]
for name in paths:
 mode,kind,blob=entries[name];assert mode in ("100644","100755") and kind=="blob"
 data=subprocess.check_output(["git","cat-file","blob",blob],cwd=ROOT);actual=(ROOT/name).read_bytes();assert actual==data,name
 written.append({"path":name,"blob":blob,"mode":mode,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()})
git("add","-f",f"--pathspec-from-file={OUT/'target-paths.nul'}","--pathspec-file-nul")
assert git("write-tree").decode().strip()==TREE
message=OUT/"recovery-commit-message.txt";message.write_text("Recover interrupted admitted root merge forward\n\nMaterialize exact root target 47a2ff90186628afafa4c01ecf7158325b0026fc after disk exhaustion. Preserve partial bytes in scratch; no reset, deletion, or history rewrite.\n")
git("commit","-F",str(message));recovery=git("rev-parse","HEAD").decode().strip();assert git("rev-parse","HEAD^{tree}").decode().strip()==TREE
git("merge","--no-ff","--no-edit",TARGET);merged=git("rev-parse","HEAD").decode().strip();assert git("rev-parse","HEAD^{tree}").decode().strip()==TREE
parents=git("rev-list","--parents","-n","1","HEAD").decode().strip().split()[1:];assert parents==[recovery,TARGET]
assert not git("status","--porcelain=v1","-uall")
report={"base":BASE,"target":TARGET,"target_tree":TREE,"recovery_commit":recovery,"merge_commit":merged,"parents":parents,"written":written,"clean":True,"original_snapshot":str(OUT/"snapshot.json"),"first_add_ignored_path_error_preserved":str(OUT/"forward-commands.json"),"no_deletions":True}
(OUT/"forward-recovery.json").write_text(json.dumps(report,indent=2)+"\n");print(json.dumps({k:v for k,v in report.items() if k!="written"}))
