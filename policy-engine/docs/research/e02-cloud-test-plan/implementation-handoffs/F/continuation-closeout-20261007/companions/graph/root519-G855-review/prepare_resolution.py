from pathlib import Path
import json,hashlib,re,difflib
D=Path('/tmp/e02-F-continuation-20261007/graph/root519-G855-review')
def sha(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def ours(b):
 out=[];state='outside'
 for ln in b.splitlines(keepends=True):
  if ln.startswith(b'<<<<<<< '):
   if state!='outside':raise ValueError('nested conflict')
   state='ours'
  elif ln.startswith(b'=======') and state=='ours':state='theirs'
  elif ln.startswith(b'>>>>>>> ') and state=='theirs':state='outside'
  elif state in ['outside','ours']:out.append(ln)
 if state!='outside':raise ValueError('unclosed conflict')
 return b''.join(out)
audit={'schema':'policyos.e02.readonly.ledger_resolution_proposal.v1','role':'scratch proposal only; publisher must ordinary merge, then verify actual frozen bytes','root':'519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82','G':'855cb26a7a2c9fea60356663cf81e7d01e20c738','virtual_tree':'9ac56f67695e9244a55c2c8a63c77263808a0588','files':[]}
for n in ['F.md','method-decisions.md']:
 r=(D/('root-'+n)).read_bytes();g=(D/('G-'+n)).read_bytes();v=(D/('virtual-'+n)).read_bytes();p=ours(v)
 (D/('proposed-'+n)).write_bytes(p)
 patch=''.join(difflib.unified_diff(r.decode().splitlines(keepends=True),p.decode().splitlines(keepends=True),fromfile='root/'+n,tofile='proposed/'+n))
 (D/(n+'.root-to-proposal.patch')).write_text(patch)
 row={'path':'policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/'+n,'root':sha(r),'G':sha(g),'virtual':sha(v),'proposed':sha(p),'conflict_hunks':v.count(b'<<<<<<< '),'markers_remaining':any(z in p for z in [b'<<<<<<< ',b'=======\n',b'>>>>>>> ']),'root_identical':r==p,'root_to_proposal_patch':str(D/(n+'.root-to-proposal.patch'))}
 if n=='method-decisions.md':
  anchor=b'<a id="methods-f"></a>'
  froot=r[r.index(anchor):];fprop=p[p.index(anchor):]
  cg=b'<a id="methods-c"></a>';prefixG=g[:g.index(anchor)];prefixP=p[:p.index(anchor)]
  CEG=g[g.index(cg):g.index(anchor)];CEP=p[p.index(cg):p.index(anchor)]
  row.update({'F_block_identical_root':froot==fprop,'F_block':sha(fprop),'current_G_C_D_E_bytes_preserved':CEG==CEP,'C_D_E_bytes':sha(CEG),'G_original_criterion_notice_preserved':g.split(b'\n\n',1)[0] in p,'F_M_anchors':re.findall(rb'<a id="f-m(\d+)"></a>',fprop)})
  row['F_M_anchors']=[x.decode() for x in row['F_M_anchors']]
 audit['files'].append(row)
audit['check']='PASS' if not any(x['markers_remaining'] for x in audit['files']) and all(x.get('current_G_C_D_E_bytes_preserved',True) for x in audit['files']) and audit['files'][1]['F_block_identical_root'] else 'FAIL'
(D/'ledger-resolution-proposal.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n');print(json.dumps(audit,ensure_ascii=False,indent=2));print((D/'method-decisions.md.root-to-proposal.patch').read_text());print('F diff:',(D/'F.md.root-to-proposal.patch').read_text())
