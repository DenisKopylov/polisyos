from pathlib import Path
import subprocess,json,hashlib,difflib
OUT=Path(__file__).parent;POST=OUT/'postimage';ROOT=Path('/workspace/e02-E-continuation-20261006');BASE='5e3e3727685132f270a3a07b9f63dd962a88cd96'
rows=[];chunks=[]
for p in sorted(POST.rglob('*')):
 if not p.is_file():continue
 relative=str(p.relative_to(POST));after=p.read_bytes()
 exists=subprocess.run(['git','-C',str(ROOT),'cat-file','-e',BASE+':'+relative],capture_output=True).returncode==0
 before=subprocess.check_output(['git','-C',str(ROOT),'show',BASE+':'+relative]) if exists else b''
 assert after!=before,relative
 rows.append({'path':relative,'new_file':not exists,'base_git_blob':subprocess.check_output(['git','-C',str(ROOT),'rev-parse',BASE+':'+relative],text=True).strip() if exists else None,'before_sha256':hashlib.sha256(before).hexdigest() if exists else None,'after_sha256':hashlib.sha256(after).hexdigest(),'bytes':len(after)})
 chunks.append('diff --git a/'+relative+' b/'+relative+'\n')
 if not exists:chunks.append('new file mode 100644\n')
 chunks.extend(difflib.unified_diff(before.decode().splitlines(keepends=True),after.decode().splitlines(keepends=True),fromfile='a/'+relative if exists else '/dev/null',tofile='b/'+relative))
patch=''.join(chunks).encode();(OUT/'owned-facade-route.patch').write_bytes(patch)
manifest={'schema':'policyos.e02.owned_facade_scratch_source_manifest.v1','base':BASE,'base_tree':'3b63e778d5b6d17b2e9edc3b4bf91af079b32eb0','source_state':'immutable scratch postimages; no implementation Git commit yet','paths':rows,'patch_sha256':hashlib.sha256(patch).hexdigest(),'patch_bytes':len(patch)}
(OUT/'postimage-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
run=subprocess.run(['git','-C',str(ROOT),'apply','--check',str(OUT/'owned-facade-route.patch')],capture_output=True)
(OUT/'apply-check.json').write_text(json.dumps({'argv':run.args,'root_HEAD':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),'exit_code':run.returncode,'stdout':run.stdout.decode(),'stderr':run.stderr.decode()},indent=2)+'\n')
print(json.dumps({'path_count':len(rows),'patch_bytes':len(patch),'patch_sha256':manifest['patch_sha256'],'git_apply_check_exit':run.returncode},indent=2))
raise SystemExit(run.returncode)
