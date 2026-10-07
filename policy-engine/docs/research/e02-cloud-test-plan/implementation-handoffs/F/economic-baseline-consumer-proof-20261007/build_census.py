from pathlib import Path
import subprocess,json,hashlib,re
root=Path('/workspace/e02-F-economics-20261006');dest=Path('/tmp/e02-F-continuation-20261007/economics')
def git(*args):return subprocess.check_output(['git',*args],cwd=root)
def bound(p):
 b=p.read_bytes();return {'path':str(p.relative_to(root)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
tracked=git('ls-files','-z').decode().split('\0');tracked=[x for x in tracked if x]
extensions={'.py','.toml','.yaml','.yml','.json','.ini','.cfg','.sh','.ts','.tsx','.js','.mjs','.cjs'}
paths=[x for x in tracked if Path(x).suffix in extensions and not x.startswith(('policy-engine/docs/','policy-engine/release-fragments/')) and (root/x).is_file()]
patterns=[r'\bpolicy_loss_fn\b',r'\bnormalized_income_budget_loss\b',r'polisyos\.foundry\.methods\.(?:loss|_internal\.loss)',r'polisyos\.foundry\.plugins\.economics\.baselines']
rows=[];matched=[]
for path in paths:
 p=root/path;entry=bound(p);entry['git_blob']=git('rev-parse','HEAD:'+path).decode().strip();rows.append(entry)
 try:lines=p.read_text().splitlines()
 except UnicodeDecodeError:continue
 hits=[{'line':i,'text':s} for i,s in enumerate(lines,1) if any(re.search(pattern,s) for pattern in patterns)]
 if hits:matched.append({**entry,'matches':hits})
receipt={'source_sha':git('rev-parse','HEAD').decode().strip(),'source_tree':git('rev-parse','HEAD^{tree}').decode().strip(),'denominator':len(rows),'suffixes':sorted(extensions),'excluded_roots':['policy-engine/docs/ (documentation/evidence, separately indexed)','policy-engine/release-fragments/ (release metadata)'],'complete_inputs':rows,'patterns':patterns,'matching_files':matched,'boundary':'Complete tracked literal source/config/FQN census. Reflection, constructed strings, untracked code and external/production callers are not proven absent. Native maintained callers/aliases are replayed; an absent production optimizer is not an original LA035 relocation blocker.'}
(dest/'baseline-consumer-census.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
locators=[]
for path in tracked:
 if not path.startswith('policy-engine/docs/') or not path.endswith(('.md','.json','.tsv','.py')) or not (root/path).is_file():continue
 p=root/path
 try:lines=p.read_text().splitlines()
 except UnicodeDecodeError:continue
 hits=[{'line':i,'text':s[:2500]} for i,s in enumerate(lines,1) if re.search(r'LA-?0(?:04|35)',s)]
 if hits:
  role='historical_frozen_preserve' if '/implementation-handoffs/' in path or '/results/' in path or '/source/' in path or '/full-run/' in path else 'root_current_caption_candidate'
  locators.append({**bound(p),'role':role,'matches':hits})
(dest/'dependent-reference-locators.json').write_text(json.dumps({'source_sha':receipt['source_sha'],'finding_ids':['LA-004','LA-035'],'denominator_tracked_paths':len(tracked),'locators':locators,'root_write_boundary':'ROOT alone changes current ledger/F.md/common current captions; every old frozen receipt remains literal. Root must classify current generated/index references versus immutable history before forward correction.'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'consumer_denominator':len(rows),'matching_files':len(matched),'reference_files':len(locators),'census_bytes':(dest/'baseline-consumer-census.json').stat().st_size,'locators_bytes':(dest/'dependent-reference-locators.json').stat().st_size}))
