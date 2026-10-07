from __future__ import annotations
import hashlib, json, os, stat
from pathlib import Path

repo = Path("/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos")
c3_rel = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/receipts/final-closeout-c3/final-native-trash.json"
c2_rel = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/receipts/cleanup-outcome-c2/cleanup-operation-242da.json"
def read_receipt(rel):
    b=(repo/rel).read_bytes(); return json.loads(b), hashlib.sha256(b).hexdigest()
c3,c3_sha=read_receipt(c3_rel); c2,c2_sha=read_receipt(c2_rel)
terms=("hatchling", "build", "pyproject_hooks", "pathspec", "trove_classifiers", "wheel", "hnswlib")
rows=[]
def lstat_record(path):
    try:
        st=os.lstat(path)
    except FileNotFoundError:
        return {"exists":False,"is_symlink":False}
    return {"exists":True,"is_symlink":stat.S_ISLNK(st.st_mode),"device":st.st_dev,"inode":st.st_ino,"mode":oct(st.st_mode)}
for item in c3.get("records",[]):
    if not isinstance(item,dict) or item.get("kind") not in ("base-environment","fresh_root_test_environment"):
        continue
    rb=item.get("readback",{}); dest=rb.get("destination"); identity=lstat_record(dest) if dest else {"exists":False}
    row={"prior_receipt":"C3","kind":item.get("kind"),"source_path":item.get("preflight",{}).get("path"),"trash_path":dest,"expected_identity":{"device":rb.get("device"),"inode":rb.get("inode")},"observed_identity":identity,"receipt_identity_match":bool(identity.get("exists") and not identity.get("is_symlink") and identity.get("device")==rb.get("device") and identity.get("inode")==rb.get("inode")),"site_packages_path":None,"direct_entry_count":None,"relevant_direct_entries":[]}
    if identity.get("exists") and not identity.get("is_symlink"):
        candidate=Path(dest)/"lib/python3.14/site-packages"
        spst=lstat_record(candidate)
        if spst.get("exists") and not spst.get("is_symlink") and stat.S_ISDIR(os.lstat(candidate).st_mode):
            row["site_packages_path"]=str(candidate); entries=[]; relevant=[]
            for ent in candidate.iterdir():
                entst=os.lstat(ent)
                if stat.S_ISLNK(entst.st_mode):
                    continue
                entries.append(ent.name)
                if any(t in ent.name.lower() for t in terms): relevant.append(ent.name)
            row["direct_entry_count"]=len(entries); row["relevant_direct_entries"]=sorted(relevant)
    rows.append(row)
for item in c2.get("moves",[]):
    if not isinstance(item,dict) or item.get("category") not in ("private_python_environment","installed_python_environment","private_build_environment"):
        continue
    dest=item.get("trash_path"); identity=lstat_record(dest) if dest else {"exists":False}
    rows.append({"prior_receipt":"C2","kind":item.get("category"),"source_path":item.get("original_path"),"trash_path":dest,"expected_identity":{"device":item.get("device"),"inode":item.get("inode")},"observed_identity":identity,"receipt_identity_match":bool(identity.get("exists") and not identity.get("is_symlink") and identity.get("device")==item.get("device") and identity.get("inode")==item.get("inode")),"site_packages_path":None,"direct_entry_count":None,"relevant_direct_entries":[],"source_absent_and_destination_inode_matches_in_receipt":item.get("source_absent_and_destination_inode_matches")})
out={"schema":"policyos.e02.c5.known_trash_readonly.v1","scope":"Only exact environment Trash paths named by the committed C2/C3 cleanup receipts; no Trash discovery, restoration, install, or deletion.","receipts":[{"path":c3_rel,"sha256":c3_sha},{"path":c2_rel,"sha256":c2_sha}],"observations":rows}
text=json.dumps(out,indent=2,sort_keys=True)+"\n"
Path(".tmp/e02-C5/raw/environment/known-trash-ro-audit.json").write_text(text)
print(text,end="")
