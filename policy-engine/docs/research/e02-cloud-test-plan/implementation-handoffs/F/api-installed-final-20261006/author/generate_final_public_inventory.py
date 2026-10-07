"""Call the existing canonical renderers for the two root-leased outputs only."""
import hashlib,json,subprocess,sys
from pathlib import Path
from dataclasses import asdict
from tools.devx.architecture import guardrails as g
root=g.REPO_ROOT.parent
sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=root,text=True).strip()
policies=g._parse_public_surface(g.DEFAULT_PUBLIC_MANIFEST)
families=g._parse_public_generated_artifact_families(g.DEFAULT_PUBLIC_MANIFEST)
inv=g.build_public_surface_inventory(policies)
encoded=g.render_public_surface_json(inv,generated_artifact_families=families)
md=g.render_public_surface_markdown(inv)
g._write_if_changed(g.DEFAULT_PUBLIC_JSON,encoded)
g._write_if_changed(g.DEFAULT_PUBLIC_MD,md)
rows=[r for p in inv for r in p.entrypoints]
violations=g._check_public_surface_contracts(inv)
record={'source_sha':sha,'source_tree':tree,'paths':[{'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (g.DEFAULT_PUBLIC_JSON,g.DEFAULT_PUBLIC_MD)],'supported_entrypoints':len(rows),'unknown_entrypoints':sum(r.export_count is None for r in rows),'candidate_names':{r.module:r.export_resolution.get('declared_export_candidates',[]) for r in rows if r.module in ('polisyos.ir.analytics','polisyos.fabric.world')},'canonical_gate_outcome':'FAIL' if violations else 'PASS','canonical_violations':[asdict(v) for v in violations],'scope':'representation generation only; complete export verdict remains canonical gate failure, candidate names are unproved source declarations, no module execution/scientific or authority assertion'}
out=Path(sys.argv[1]).resolve();assert out.is_relative_to(Path('/tmp')) and not out.exists();out.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({'source_sha':sha,'source_tree':tree,'supported_entrypoints':len(rows),'unknown_entrypoints':record['unknown_entrypoints'],'canonical_violations':len(violations),'outputs':record['paths']}))
