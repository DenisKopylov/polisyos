import json,pathlib,subprocess,sys
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.loading.norm_pack import NormPack,NormRule,RuleType
from polisyos.lex.legal_evaluation.impact_diff import NormImpactAnalyzer
root=pathlib.Path('/workspace/e02-F-20261006-receipts/lex/fresh-reader-cas'); cas=FileSystemCAS(root)
def pack(id,threshold):return NormPack(pack_id=id,jurisdiction='ua',norms=[NormRule(norm_id='n.income',description='Synthetic income floor',rule_type=RuleType.OBLIGATION,backend_refs=['expr_ast'],backend_metadata={'must':f'income >= {threshold}'})])
r=NormImpactAnalyzer(cas,passes=('legal','legal'),legal_backend='expr_ast').analyze(pack('synthetic.old',1),pack('synthetic.new',3),context={'income':2})
code='''import json,sys
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.canon import from_canonical_bytes
from polisyos.lex.legal_evaluation.impact_diff import NormImpactReport
from polisyos.lex.normpack.diff import NormDiff
from polisyos.lex.simulator.cli import render_impact_markdown
s=FileSystemCAS(sys.argv[1]);r=NormImpactReport.model_validate(from_canonical_bytes(s.get_bytes(ArtifactID.model_validate(sys.argv[2]))));d=NormDiff.model_validate(from_canonical_bytes(s.get_bytes(ArtifactID.model_validate(r.norm_diff_ref))));assert r.new_blockers==1 and r.passes_executed==['legal'];assert d.modified_count==1;assert all(t.estimated_direction=='unknown' for t in r.affected_kpis);assert 'Candidate Impact Topics' in render_impact_markdown(r);print(json.dumps({'passes':r.passes_executed,'blockers':r.new_blockers,'diff_ref':r.norm_diff_ref,'topics':[t.kpi_id for t in r.affected_kpis],'authority':'synthetic topic/compliance comparison only','reader_origin':sys.modules['polisyos.lex.legal_evaluation.impact_diff'].__file__}))'''
a=subprocess.run([sys.executable,'-c',code,str(root),r.cas_artifact_id],capture_output=True,text=True);print(a.stdout,end='');print(a.stderr,end='',file=sys.stderr);raise SystemExit(a.returncode)
