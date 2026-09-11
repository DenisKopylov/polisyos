"""Read-only worktree audit; prune is called exclusively with --dry-run."""
from pathlib import Path
import subprocess, json, hashlib, os, datetime
from collections import Counter
ROOT=Path(__file__).resolve().parents[6]
OUT=Path(__file__).resolve().parent
CMDS=[]
def command(*args):
 p=subprocess.run(['git',*args],cwd=ROOT,capture_output=True,text=True)
 CMDS.append({'argv':['git',*args],'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
 return p
common=Path(command('rev-parse','--path-format=absolute','--git-common-dir').stdout.strip())
main=command('rev-parse','refs/heads/main').stdout.strip()
time=datetime.datetime.now(datetime.timezone.utc).isoformat()
def metadata():
 result={}
 for p in sorted((common/'worktrees').iterdir()):
  if p.is_dir():
   result[p.name]={}
   for field in ('gitdir','HEAD','commondir','locked'):
    q=p/field
    try: result[p.name][field]=q.read_text()
    except FileNotFoundError: result[p.name][field]=None
    except OSError as e: result[p.name][field]={'error':str(e)}
 return result
before=metadata()
porcelain=command('worktree','list','--porcelain','-z').stdout
blocks=[]; current={}
for token in porcelain.split('\0'):
 if not token:
  if current: blocks.append(current);current={}
  continue
 key,_,value=token.partition(' ')
 current[key]=value
if current:blocks.append(current)
dry=command('worktree','prune','--dry-run','--verbose')
rows=[]
for name,values in before.items():
 ptr=values['gitdir']
 if not isinstance(ptr,str):
  rows.append({'registration':name,'ambiguous_gitdir':ptr});continue
 gitfile=Path(ptr.strip())
 directory=gitfile.parent
 head=values['HEAD']
 branch=head.removeprefix('ref: ').strip() if isinstance(head,str) and head.startswith('ref: ') else None
 if branch:
  tip=command('rev-parse','--verify',branch)
  if tip.returncode: disposition='gone'; sha=None
  else:
   sha=tip.stdout.strip()
   ancestor=command('merge-base','--is-ancestor',sha,main)
   disposition={0:'merged_into_pinned_main',1:'unmerged'}.get(ancestor.returncode,'ambiguous')
 else:
  sha=head.strip() if isinstance(head,str) else None
  ancestor=command('merge-base','--is-ancestor',sha,main) if sha else None
  disposition='detached_'+({0:'commit_in_main',1:'commit_not_in_main'}.get(ancestor.returncode,'ambiguous') if ancestor else 'ambiguous')
 match=[b for b in blocks if b.get('worktree')==str(directory)]
 rows.append({'registration':name,'expected_directory':str(directory),'directory_exists':directory.exists(),'gitfile_exists':gitfile.exists(),'branch':branch,'tip':sha,'branch_disposition':disposition,'locked':values['locked'],'porcelain_matches':match,'dry_run_selected':any(line.startswith('Removing worktrees/'+name+':') for line in (dry.stdout+dry.stderr).splitlines())})
after=metadata()
# Search complete directory entries within declared scope; don't follow symlinks.
# Excluded machinery can contain arbitrary bytes, so this is explicitly a bounded negative.
excluded_names={'.git','node_modules','.venv','venv','__pycache__','.cache','.npm','.pnpm-store','.rustup','.cargo','.Trash','Library','Photos Library.photoslibrary'}
scanroots=[Path('/Users/deniskopylov'),Path('/private/tmp')]
skips=[];errors=[];pointers=[];directories=0;entries=0
stack=list(scanroots)
while stack:
 d=stack.pop();directories+=1
 try:
  with os.scandir(d) as it: children=list(it)
 except OSError as e: errors.append({'path':str(d),'error':str(e)});continue
 for ent in children:
  entries+=1
  p=Path(ent.path)
  try:
   if ent.name=='.git' and ent.is_file(follow_symlinks=False):
    try:
     value=p.read_text().strip()
     if value.startswith('gitdir:'):
      target=(p.parent/value[7:].strip()).resolve()
      if target.parent==common/'worktrees':pointers.append({'path':str(p),'target':str(target),'registration':target.name})
    except (OSError,UnicodeError) as e: errors.append({'path':str(p),'error':str(e)})
   elif ent.is_dir(follow_symlinks=False):
    if ent.name in excluded_names:skips.append(str(p))
    else:stack.append(p)
   elif ent.is_symlink():skips.append(str(p)+' [symlink not followed]')
  except OSError as e:errors.append({'path':str(p),'error':str(e)})
for row in rows:
 row['off_expected_git_pointers']=[p for p in pointers if p['registration']==row['registration'] and str(Path(p['path']).parent)!=row.get('expected_directory')]
final=metadata()
summary={'time_utc':time,'main':main,'common_dir':str(common),'porcelain_total':len(blocks),'admin_plus_main_total':len(rows)+1,'path_set_equal':set(b['worktree'] for b in blocks)=={str(common.parent)}|{r.get('expected_directory') for r in rows},'metadata_stable_through_prune_dry_run':before==after,'metadata_stable_through_off_path_scan':before==final,'main_stable':command('rev-parse','refs/heads/main').stdout.strip()==main,'linked_registration_count':len(rows),'missing_directory_count':sum(not r.get('directory_exists',True) for r in rows),'dry_run_selected_count':sum(r.get('dry_run_selected',False) for r in rows),'selected_branch_distribution':dict(Counter(r['branch_disposition'] for r in rows if r.get('dry_run_selected'))),'selected_existing_directory_count':sum(r.get('dry_run_selected',False) and r.get('directory_exists',False) for r in rows),'scan':{'roots':[str(x) for x in scanroots],'directories_visited':directories,'directory_entries_inspected':entries,'excluded_names':sorted(excluded_names),'excluded_path_count':len(skips),'error_count':len(errors),'errors':errors,'all_repo_git_pointers':pointers},'registrations':rows}
raw={'summary':summary,'commands':CMDS,'porcelain_blocks':blocks,'metadata_before':before,'metadata_after':after,'metadata_final':final,'excluded_paths':skips}
p=OUT/'raw/census.json';p.write_text(json.dumps(raw,indent=2)+'\n')
summary['raw_receipt']={'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
raise SystemExit(0 if before==after==final and summary['path_set_equal'] else 2)
