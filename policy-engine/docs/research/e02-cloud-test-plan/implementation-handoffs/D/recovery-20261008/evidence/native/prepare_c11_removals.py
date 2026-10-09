import hashlib,json,pathlib,subprocess,sys
base=pathlib.Path(sys.argv[1]);prefix=pathlib.Path(sys.argv[2])
specs={
 'intake-binding':('policy-engine/src/polisyos/scientist/methods/search/uncertainty.py',[(f'if {x}:',f'if False and {x}:') for x in ['basis.subject_ref != expected_subject_ref','observation.basis_ref != expected_basis_ref','observation.producer_ref != basis.producer_ref','observation.envelope != expected_envelope']]),
 'cache-selected-view':('policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py',[('return artifact_ref_identity_key(value)','return str(value.artifact_id)  # retained artifact_ref_identity_key marker')]),
 'berl-unavailable':('policy-engine/src/polisyos/scientist/validation/phase5_preflight.py',[('blockers.append("Explanation BERL validation unavailable or input malformed.")','warnings.append("Explanation BERL validation unavailable or input malformed.")')]),
 'builtin-freshness':('policy-engine/src/polisyos/scientist/nodes/components.py',[('scientist_node_component(node, node_factory=type(node))','scientist_node_component(node, node_factory=lambda node=node: node)  # type(node) retained')]),
 'promotion-no-effect':('policy-engine/src/polisyos/scientist/methods/search/funnel/level6_promotion.py',[('            terminal_action = "defer_to_human"\n            failure_cards.append(_owner_recheck_failure_card())','            promotion_payload = self._promotion_runner(candidate, context)\n            terminal_action = "defer_to_human"\n            failure_cards.append(_owner_recheck_failure_card())')]),
}
for name,(path,changes) in specs.items():
 out=prefix/name;subprocess.run([sys.executable,str(prefix.parent/'clone_removal.py'),'--source',str(base),'--out',str(out)],check=True)
 p=out/path;pre=p.read_text();post=pre
 for old,new in changes:
  assert post.count(old)==1,(name,old,post.count(old));post=post.replace(old,new)
 p.write_text(post)
 (prefix/(name+'-mutation.json')).write_text(json.dumps({'baseline':str(base),'path':path,'preimage_sha256':hashlib.sha256(pre.encode()).hexdigest(),'postimage_sha256':hashlib.sha256(post.encode()).hexdigest(),'replacements':changes,'purpose':'remove runtime property while keeping named markers/refs/testing inputs intact'},indent=2)+'\n')
