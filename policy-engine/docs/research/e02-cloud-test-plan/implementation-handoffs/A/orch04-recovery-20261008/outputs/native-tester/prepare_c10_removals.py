import hashlib,json,pathlib,subprocess,sys
base=pathlib.Path(sys.argv[1]);prefix=pathlib.Path(sys.argv[2])
specs={
 'b36-required':('policy-engine/src/polisyos/runtime/quality/generation_cycle.py',[("\"value_available_data_modalities\": profile.available_data_modalities,","\"value_required_data_modalities\": profile.available_data_modalities,  # value_available_data_modalities marker retained")]),
 'child-semantics':('policy-engine/src/polisyos/runtime/quality/design_generation.py',[("        if semantic_ref not in by_semantics:\n", "        semantic_ref = gy_content_hash(candidate.model_dump(mode=\"json\"))\n        if semantic_ref not in by_semantics:\n")]),
 'capsule-current-job':('policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py',[("        \"\"\"Resolve complete child evidence afresh before candidate execution.\"\"\"\n", "        \"\"\"Resolve complete child evidence afresh before candidate execution.\"\"\"\n        return  # current-owner methods and markers retained below\n")]),
 'capsule-reader-binding':('policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py',[("        if (capsule.node_ref, capsule.parent_ref, capsule.problem) != (", "        if False and (capsule.node_ref, capsule.parent_ref, capsule.problem) != (")]),
 'partial-frontier':('policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py',[("                        *child_refs[child_index + 1 :],", "                        *(),  # child_refs[child_index + 1 :] retained marker")]),
}
for name,(path,changes) in specs.items():
 out=prefix/name;subprocess.run([sys.executable,str(prefix.parent/'clone_removal.py'),'--source',str(base),'--out',str(out)],check=True)
 p=out/path;pre=p.read_text();post=pre
 for old,new in changes:
  assert post.count(old)==1,(name,old,post.count(old));post=post.replace(old,new)
 p.write_text(post)
 (prefix/(name+'-mutation.json')).write_text(json.dumps({'baseline':str(base),'path':path,'preimage_sha256':hashlib.sha256(pre.encode()).hexdigest(),'postimage_sha256':hashlib.sha256(post.encode()).hexdigest(),'replacements':changes,'purpose':'remove runtime property while keeping named markers/refs/testing inputs intact'},indent=2)+'\n')
